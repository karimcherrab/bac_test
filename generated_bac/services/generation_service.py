from django.db import transaction

from course.models import Branch, Chapter

from ..models import GeneratedBacExercise
from .groq_client import GroqJSONClient
from .prompt_builder import BacPromptBuilder
from .reference_selector import BacReferenceSelector
from .validators import (
    ExerciseValidator,
    SolutionValidator,
)


class BacExerciseGenerationService:
    def __init__(self):
        self.selector = BacReferenceSelector()
        self.prompt_builder = BacPromptBuilder()

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
        chapter = Chapter.objects.get(
            id=chapter_id,
        )

        branch = Branch.objects.get(
            code=branch_code,
        )

        selected_exercises = self.selector.select(
            chapter_id=chapter.id,
            branch_code=branch.code,
            limit=references_count,
            strategy=selection_strategy,
        )

        compact_references = (
            self.selector
            .compact_for_exercise_generation(
                selected_exercises
            )
        )

        system_prompt, user_prompt = (
            self.prompt_builder
            .build_exercise_prompt(
                chapter_title=chapter.title,
                branch_name=branch.name,
                references=compact_references,
            )
        )

        generated_data, model_name = (
            GroqJSONClient().generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.35,
                max_tokens=5500,
            )
        )

        generated_data = (
            ExerciseValidator().validate(
                generated_data
            )
        )

        generated = (
            GeneratedBacExercise.objects.create(
                student=student,
                chapter=chapter,
                branch=branch,
                title=generated_data["title"],
                exercise=generated_data,
                solution={},
                reference_exercise_ids=[
                    exercise.id
                    for exercise in selected_exercises
                ],
                selection_strategy=selection_strategy,
                model_exercise=model_name,
                status="exercise_ready",
            )
        )

        return generated

    @transaction.atomic
    def generate_solution(
        self,
        *,
        generated_exercise: GeneratedBacExercise,
        regenerate: bool = False,
    ) -> GeneratedBacExercise:
        if (
            generated_exercise.solution
            and not regenerate
        ):
            return generated_exercise

        style_references = (
            self.selector
            .compact_for_solution_style(
                generated_exercise
                .reference_exercise_ids,
                limit=2,
            )
        )

        system_prompt, user_prompt = (
            self.prompt_builder
            .build_solution_prompt(
                generated_exercise_id=(
                    generated_exercise.id
                ),
                chapter_title=(
                    generated_exercise
                    .chapter.title
                ),
                branch_name=(
                    generated_exercise
                    .branch.name
                ),
                exercise=(
                    generated_exercise.exercise
                ),
                solution_style_references=(
                    style_references
                ),
            )
        )

        generated_solution, model_name = (
            GroqJSONClient().generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=7500,
            )
        )

        generated_solution = (
            SolutionValidator().validate(
                generated_solution,
                exercise_id=(
                    generated_exercise.id
                ),
                exercise=(
                    generated_exercise.exercise
                ),
            )
        )

        generated_exercise.solution = (
            generated_solution
        )
        generated_exercise.model_solution = (
            model_name
        )
        generated_exercise.status = (
            "solution_ready"
        )
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
