from __future__ import annotations

from django.db import transaction
from .exceptions import AIResponseError
import secrets
import json
from .statement_visual_policy import reference_policy, apply_policy
from .subject_resolver import resolve_subject
from .physics_prompt_builder import PhysicsPromptBuilder, UNIT_RULES
from .science_prompt_builder import SciencePromptBuilder
from .science_documents import SCIENCE_UNITS, build_catalog, validate_exercise as validate_science_exercise, validate_solution as validate_science_solution, validate_reexplanation as validate_science_reexplanation
from .physics_policy import unit_code, physics_policy, validate_physics_exercise

from course.models import Branch, Chapter

from ..models import (
    GeneratedBacExercise,
    GeneratedBacQuestionReExplanation,
)
from .groq_client import GroqJSONClient
from .prompt_builder import BacPromptBuilder
from .reference_selector import BacReferenceSelector
from .validators import (
    ExerciseValidator,
    QuestionSolutionReExplanationValidator,
    SolutionValidator,
)


class BacExerciseGenerationService:
    def __init__(self):
        self.selector = BacReferenceSelector()
        self.prompt_builder = BacPromptBuilder()

    @property
    def ai_client(self):
        return GroqJSONClient()

    def validated_request(self, *, system_prompt, user_prompt, validator, max_tokens):
        # At most one content repair; transport/rate-limit failures are not retried here.
        for attempt in range(2):
            data, model = self.ai_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt,
                                                       temperature=0.25, max_tokens=max_tokens)
            try:
                return validator(data), model
            except AIResponseError as exc:
                if attempt:
                    raise AIResponseError("تعذر تجهيز محتوى مكتمل. حاول إنشاء التمرين مرة أخرى.") from exc
                user_prompt += "\nأعد JSON كاملًا وصحح هذا الخطأ: " + str(exc)[:500]


    def _configure_saved_subject(self, record):
        metadata = record.generation_metadata or {}
        if metadata.get("subject_code") == "natural_sciences":
            self.prompt_builder=SciencePromptBuilder(metadata["science_document_catalog"])
        elif metadata.get("subject_code") == "physics":
            code=metadata.get("unit_code", "")
            if code not in UNIT_RULES:
                raise AIResponseError("رمز وحدة الفيزياء غير محفوظ في هذا التمرين.")
            self.prompt_builder=PhysicsPromptBuilder(code)
        else:
            self.prompt_builder=BacPromptBuilder()

    def generate_exercise(
        self,
        *,
        student,
        chapter_id: int,
        branch_code: str,
        subject_code: str = "auto",
        references_count: int = 1,
        selection_strategy: str = "diverse_random",
    ) -> GeneratedBacExercise:
        chapter = Chapter.objects.get(id=chapter_id)
        branch = Branch.objects.get(code=branch_code)

        # Rotate through the student's recent references when alternatives exist.
        recent = GeneratedBacExercise.objects.filter(student=student, chapter=chapter, branch=branch).order_by('-created_at')[:10]
        exclude_ids = {pk for item in recent for pk in item.reference_exercise_ids}
        selected_exercises = self.selector.select(
            chapter_id=chapter.id,
            branch_code=branch.code,
            limit=1,
            exclude_ids=exclude_ids,
            subject_code=subject_code,
            strategy=selection_strategy,
        )

        subject_code = resolve_subject(selected_exercises[0].content, subject_code)
        if subject_code == "natural_sciences":
            selected_exercises = self.selector.select(chapter_id=chapter.id,branch_code=branch.code,exclude_ids=exclude_ids,subject_code=subject_code)
        science = subject_code == "natural_sciences"
        physics = subject_code == "physics"
        catalog = []
        detected_unit = (selected_exercises[0].content or {}).get("chapter_code", "")
        if not science and detected_unit in SCIENCE_UNITS:
            raise AIResponseError("هذه وحدة علوم؛ أرسل subject_code=natural_sciences.")
        if not physics and detected_unit in UNIT_RULES:
            raise AIResponseError("هذه وحدة فيزياء؛ أرسل subject_code=physics من الواجهة.")
        if not physics and not science:
            self.prompt_builder = BacPromptBuilder()
        if physics:
            detected_unit = unit_code(selected_exercises[0])
            self.prompt_builder = PhysicsPromptBuilder(detected_unit)

        if science:
            catalog=build_catalog(selected_exercises[0].content)
            self.prompt_builder=SciencePromptBuilder(catalog)

        compact_references = [] if science else self.selector.compact_for_exercise_generation(
            selected_exercises
        )

        system_prompt, user_prompt = self.prompt_builder.build_exercise_prompt(
            chapter_title=chapter.title,
            branch_name=branch.name,
            references=compact_references,
        )

        policy = {"subject":"natural_sciences","reuse_existing_images":True} if science else (physics_policy(selected_exercises[0].content) if physics else reference_policy(selected_exercises[0].content))
        user_prompt += "\nسياسة الرسومات المعطاة من المرجع (إلزامية): " + json.dumps(policy)
        user_prompt += "\nرمز تنويع: " + secrets.token_hex(5)
        generated_data, model_name = self.validated_request(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            validator=(lambda data: validate_science_exercise(data,catalog)) if science else ((lambda data: validate_physics_exercise(data, policy)) if physics else (lambda data: ExerciseValidator().validate(apply_policy(data, policy)))),
            max_tokens=4200,
        )


        return GeneratedBacExercise.objects.create(
            student=student,
            chapter=chapter,
            branch=branch,
            title=generated_data["title"],
            exercise=generated_data,
            solution={},
            generation_metadata={"version": "bac-prototype-v5", "subject_code": subject_code, "unit_code": detected_unit, "statement_visual_policy": policy, "science_document_catalog": catalog},
            reference_exercise_ids=[item.id for item in selected_exercises],
            selection_strategy="random",
            model_exercise=model_name,
            model_solution="",
            status="exercise_ready",
            generation_error="",
        )

    def generate_solution(
        self,
        *,
        generated_exercise: GeneratedBacExercise,
        regenerate: bool = False,
    ) -> GeneratedBacExercise:
        from .solution_chunks import advance
        return advance(self,generated_exercise,regenerate)


    def re_explain_solution_question(
        self,
        *,
        generated_exercise: GeneratedBacExercise,
        student,
        question_id: str,
    ) -> GeneratedBacQuestionReExplanation:
        self._configure_saved_subject(generated_exercise)
        exercise = generated_exercise.exercise
        solution = generated_exercise.solution

        if not isinstance(exercise, dict):
            raise ValueError(
                "exercise يجب أن يكون JSON object."
            )

        if not isinstance(solution, dict) or not solution:
            raise ValueError(
                "يجب إنشاء الحل أولًا قبل طلب إعادة شرحه."
            )

        questions = exercise.get("questions", [])
        if not isinstance(questions, list):
            questions = []

        target_question = None
        for question in questions:
            if not isinstance(question, dict):
                continue
            if str(question.get("id", "")) == str(question_id):
                target_question = question
                break

        if target_question is None:
            raise ValueError(
                "السؤال غير موجود داخل التمرين."
            )

        solution_questions = solution.get(
            "questions",
            [],
        )
        if not isinstance(solution_questions, list):
            solution_questions = []

        target_solution = None
        for item in solution_questions:
            if not isinstance(item, dict):
                continue
            if str(
                item.get("question_id", item.get("id", ""))
            ) == str(question_id):
                target_solution = item
                break

        if target_solution is None:
            raise ValueError(
                "لا يوجد حل محفوظ لهذا السؤال."
            )

        system_prompt, user_prompt = (
            self.prompt_builder
            .build_solution_re_explanation_prompt(
                exercise_title=str(
                    exercise.get(
                        "title",
                        generated_exercise.title,
                    )
                ),
                statement=str(
                    exercise.get("statement", "")
                ),
                question=target_question,
                original_solution=target_solution,
            )
        )

        generated, model_name = (
            self.ai_client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.04,
                max_tokens=3000,
            )
        )

        if isinstance(self.prompt_builder,SciencePromptBuilder):
            cleaned=validate_science_reexplanation(generated,catalog=generated_exercise.generation_metadata["science_document_catalog"],question=target_question)
        else:
            cleaned=QuestionSolutionReExplanationValidator().validate(generated,question_id=str(question_id))

        with transaction.atomic():
            GeneratedBacExercise.objects.select_for_update().get(pk=generated_exercise.pk)
            # نحسب رقم المحاولة داخل transaction حتى يبقى التاريخ مرتبًا.
            last_attempt = (
                GeneratedBacQuestionReExplanation.objects
                .filter(
                    generated_exercise=generated_exercise,
                    question_id=str(question_id),
                )
                .order_by("-attempt_number")
                .values_list(
                    "attempt_number",
                    flat=True,
                )
                .first()
            )
    
            attempt_number = int(last_attempt or 0) + 1
    
            return (
                GeneratedBacQuestionReExplanation.objects
                .create(
                    student=student,
                    generated_exercise=generated_exercise,
                    question_id=str(question_id),
                    attempt_number=attempt_number,
                    explanation=cleaned,
                    model_name=model_name,
                )
            )
