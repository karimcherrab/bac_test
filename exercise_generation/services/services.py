from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from course.models import Axis
from exercise_generation.models import GeneratedExercise
from exercise_generation.services.ai_generator import ExerciseAIGenerator
from exercise_generation.services.bac_reference_builder import get_axis_bac_references
from exercise_generation.services.context_builder import build_compact_lesson_context
from exercise_generation.services.exceptions import (
    AxisNotFoundError,
    EmptyAxisContentError,
    ExerciseGenerationError,
    ExerciseValidationError,
)
from exercise_generation.services.graph_engine import axis_requires_graph, ensure_graph_payload
from exercise_generation.services.prompts import build_bac_like_exercise_prompt
from exercise_generation.services.validators import validate_bac_like_exercise


class NoBacReferenceQuestionsError(ExerciseGenerationError):
    pass


class ExerciseGenerationService:
    MAX_GENERATION_ATTEMPTS = 3

    def __init__(self):
        self.generator = ExerciseAIGenerator()

    def generate(
        self,
        *,
        axis_id: int,
        count: int,
        student=None,
        save_to_database: bool = True,
    ) -> list[GeneratedExercise]:
        axis = self._get_axis(axis_id)
        lesson_context = build_compact_lesson_context(
            self._get_lesson_content(axis)
        )
        previous_titles = self._existing_titles(axis, student)
        generated_items: list[GeneratedExercise] = []
        used_reference_ids: list[int] = []

        for exercise_number in range(1, count + 1):
            references, reference_ids = get_axis_bac_references(
                axis=axis,
                exclude_ids=used_reference_ids,
                limit=3,
            )

            if not references:
                references, reference_ids = get_axis_bac_references(
                    axis=axis,
                    exclude_ids=[],
                    limit=3,
                )

            if not references:
                raise NoBacReferenceQuestionsError(
                    "لا توجد أسئلة بكالوريا مرتبطة بهذا المحور نفسه. "
                    "أضف Question بقيمة axis الحالية وquestion_type='bac'."
                )

            used_reference_ids.extend(reference_ids)
            result = self._generate_valid_exercise(
                axis=axis,
                lesson_context=lesson_context,
                references=references,
                previous_titles=previous_titles,
                exercise_number=exercise_number,
            )

            normalized = result["exercise"]
            previous_titles.append(normalized["title"])
            raw_response = self._enriched_raw_response(
                result["raw_ai_response"],
                normalized,
                reference_ids,
            )
            kwargs = self._model_kwargs(
                axis=axis,
                student=student,
                exercise=normalized,
                model_name=result["model_name"],
                raw_ai_response=raw_response,
            )

            instance = (
                self._save_one(**kwargs)
                if save_to_database
                else GeneratedExercise(**kwargs)
            )
            generated_items.append(instance)

        return generated_items

    def _generate_valid_exercise(
        self,
        *,
        axis: Axis,
        lesson_context: dict[str, Any],
        references: list[dict[str, Any]],
        previous_titles: list[str],
        exercise_number: int,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_GENERATION_ATTEMPTS + 1):
            compact_mode = attempt > 1
            prompt = build_bac_like_exercise_prompt(
                axis_title=axis.title,
                axis_tag=axis.tag,
                lesson_context=lesson_context,
                bac_references=references,
                previous_titles=previous_titles,
                exercise_number=exercise_number,
                compact_mode=compact_mode,
                force_graph=axis_requires_graph(axis),
                previous_error=str(last_error or ""),
            )

            try:
                generated = self.generator.generate_one(
                    prompt=prompt,
                    max_output_tokens=3200 if compact_mode else 3800,
                )
                graph_ready = ensure_graph_payload(
                    generated.exercise,
                    axis=axis,
                )
                validated = validate_bac_like_exercise(graph_ready)
                return {
                    "exercise": validated,
                    "model_name": generated.model,
                    "raw_ai_response": generated.raw_response,
                }
            except (ExerciseValidationError, ExerciseGenerationError) as exc:
                last_error = exc

        raise ExerciseValidationError(
            "فشل إنشاء تمرين صالح بعد ثلاث محاولات.",
            errors=[str(last_error)] if last_error else [],
        )

    @staticmethod
    def _enriched_raw_response(
        original: dict[str, Any],
        normalized: dict[str, Any],
        reference_ids: list[int],
    ) -> dict[str, Any]:
        payload = dict(original) if isinstance(original, dict) else {}
        payload["normalized_exercise"] = {
            **normalized,
            "reference_question_ids": list(reference_ids),
        }
        payload["reference_question_ids"] = list(reference_ids)
        return payload

    @staticmethod
    def _first_common_mistake(value: Any) -> str:
        if not isinstance(value, list):
            return ""
        for item in value:
            if not isinstance(item, dict):
                continue
            mistake = str(item.get("mistake") or "").strip()
            correction = str(item.get("correction") or "").strip()
            if mistake and correction:
                return f"{mistake}\nالتصحيح: {correction}"
            if mistake:
                return mistake
        return ""

    def _model_kwargs(
        self,
        *,
        axis: Axis,
        student,
        exercise: dict[str, Any],
        model_name: str,
        raw_ai_response: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "axis": axis,
            "student": student,
            "title": exercise["title"],
            "question": exercise["question"],
            "difficulty": "medium",
            "exercise_type": "bac_like_axis_only",
            "skill": exercise.get("skill", ""),
            "hints": exercise.get("hints", []),
            "solution_steps": exercise.get("solution_steps", []),
            "final_answer": exercise.get("final_answer", ""),
            "verification": exercise.get("verification", ""),
            "common_mistake": self._first_common_mistake(
                exercise.get("common_mistakes")
            ),
            "requires_graph": bool(exercise.get("requires_graph", False)),
            "graph_data": exercise.get("graph_data", {}),
            "model_name": model_name,
            "raw_ai_response": raw_ai_response,
        }

    @staticmethod
    def _get_axis(axis_id: int) -> Axis:
        try:
            return Axis.objects.select_related(
                "chapter",
                "chapter__subject",
            ).get(
                id=axis_id,
                is_active=True,
                chapter__is_active=True,
            )
        except Axis.DoesNotExist as exc:
            raise AxisNotFoundError("المحور غير موجود أو غير نشط.") from exc

    @staticmethod
    def _get_lesson_content(axis: Axis) -> dict[str, Any]:
        content = axis.content
        if not content:
            raise EmptyAxisContentError("محتوى المحور فارغ.")
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {
                    "axis_title": axis.title,
                    "lesson_text": content[:1800],
                }
        raise EmptyAxisContentError("صيغة محتوى المحور غير مدعومة.")

    @staticmethod
    def _existing_titles(axis: Axis, student) -> list[str]:
        queryset = GeneratedExercise.objects.filter(axis=axis, is_active=True)
        if student and getattr(student, "is_authenticated", False):
            queryset = queryset.filter(student=student)
        return list(
            queryset.order_by("-created_at").values_list("title", flat=True)[:12]
        )

    @transaction.atomic
    def _save_one(self, **kwargs) -> GeneratedExercise:
        return GeneratedExercise.objects.create(**kwargs)
