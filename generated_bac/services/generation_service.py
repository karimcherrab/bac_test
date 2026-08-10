from __future__ import annotations

from django.db import transaction

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
        self.ai_client = GroqJSONClient()

    @transaction.atomic
    def generate_exercise(
        self,
        *,
        student,
        chapter_id: int,
        branch_code: str,
        references_count: int = 3,
        selection_strategy: str = "diverse_random",
    ) -> GeneratedBacExercise:
        chapter = Chapter.objects.get(id=chapter_id)
        branch = Branch.objects.get(code=branch_code)

        selected_exercises = self.selector.select(
            chapter_id=chapter.id,
            branch_code=branch.code,
            limit=references_count,
            strategy=selection_strategy,
        )

        compact_references = self.selector.compact_for_exercise_generation(
            selected_exercises
        )

        system_prompt, user_prompt = self.prompt_builder.build_exercise_prompt(
            chapter_title=chapter.title,
            branch_name=branch.name,
            references=compact_references,
        )

        generated_data, model_name = self.ai_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.12,
            max_tokens=4200,
        )

        generated_data = ExerciseValidator().validate(generated_data)

        return GeneratedBacExercise.objects.create(
            student=student,
            chapter=chapter,
            branch=branch,
            title=generated_data["title"],
            exercise=generated_data,
            solution={},
            reference_exercise_ids=[item.id for item in selected_exercises],
            selection_strategy=selection_strategy,
            model_exercise=model_name,
            model_solution="",
            status="exercise_ready",
            generation_error="",
        )

    @transaction.atomic
    def generate_solution(
        self,
        *,
        generated_exercise: GeneratedBacExercise,
        regenerate: bool = False,
    ) -> GeneratedBacExercise:
        if generated_exercise.solution and not regenerate:
            return generated_exercise

        exercise_payload = generated_exercise.exercise
        if not isinstance(exercise_payload, dict):
            raise ValueError("exercise يجب أن يكون JSON object.")

        system_prompt, user_prompt = self.prompt_builder.build_solution_prompt(
            generated_exercise_id=generated_exercise.id,
            exercise=exercise_payload,
        )

        generated_solution, model_name = self.ai_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.06,
            max_tokens=5600,
        )

        generated_solution = SolutionValidator().validate(
            generated_solution,
            exercise_id=generated_exercise.id,
            exercise=exercise_payload,
        )

        generated_exercise.solution = generated_solution
        generated_exercise.model_solution = model_name
        generated_exercise.status = "solution_ready"
        generated_exercise.generation_error = ""
        generated_exercise.save(
            update_fields=[
                "solution",
                "model_solution",
                "status",
                "generation_error",
                "updated_at",
            ]
        )
        return generated_exercise


    @transaction.atomic
    def re_explain_solution_question(
        self,
        *,
        generated_exercise: GeneratedBacExercise,
        student,
        question_id: str,
    ) -> GeneratedBacQuestionReExplanation:
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

        cleaned = (
            QuestionSolutionReExplanationValidator()
            .validate(
                generated,
                question_id=str(question_id),
            )
        )

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
