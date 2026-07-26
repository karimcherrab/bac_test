from typing import Any
from django.db import transaction
from course.models import ReExplainStepHistory


class ReExplainStepHistoryService:
    MAX_EXPLANATIONS = 3

    @staticmethod
    def normalize_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        value = str(value).strip()
        return value or default

    @classmethod
    @transaction.atomic
    def save_history(cls, *, student, step: dict, axis, student_question: str, generated_result: dict) -> dict:
        if not getattr(student, "is_authenticated", False):
            raise ValueError("التلميذ غير مسجل الدخول.")
        if axis is None or not isinstance(step, dict) or not isinstance(generated_result, dict):
            raise ValueError("بيانات الحفظ غير صحيحة.")

        step_id = cls.normalize_text(step.get("id"))
        if not step_id:
            raise ValueError("معرف المرحلة غير موجود.")

        answer = generated_result.get("answer")
        if (
            not isinstance(answer, dict)
            or answer.get("type") not in {"explanation", "example"}
            or not cls.normalize_text(answer.get("content"))
        ):
            raise ValueError("جواب المساعدة غير صالح للحفظ.")

        queryset = ReExplainStepHistory.objects.select_for_update().filter(
            student=student, axis=axis, step_id=step_id
        ).order_by("-created_at", "-id")

        existing_ids = list(queryset.values_list("id", flat=True))
        replaced_oldest = len(existing_ids) >= cls.MAX_EXPLANATIONS
        ids_to_delete = existing_ids[cls.MAX_EXPLANATIONS - 1 :]
        if ids_to_delete:
            ReExplainStepHistory.objects.filter(id__in=ids_to_delete).delete()

        history = ReExplainStepHistory.objects.create(
            student=student,
            axis=axis,
            step_id=step_id,
            step_title=cls.normalize_text(step.get("title"), generated_result.get("step_title", "مرحلة من الدرس")),
            step_type=cls.normalize_text(step.get("type")),
            step_data=step,
            student_question=cls.normalize_text(student_question),
            answer=answer,
            model_name=cls.normalize_text(generated_result.get("model")),
        )

        count = ReExplainStepHistory.objects.filter(
            student=student, axis=axis, step_id=step_id
        ).count()
        return {"history": history, "replaced_oldest": replaced_oldest, "count": count}

    @classmethod
    def get_student_history(cls, *, student, step_id: str | None = None, axis_id: int | None = None):
        queryset = ReExplainStepHistory.objects.select_related("axis").filter(student=student)
        normalized_step_id = cls.normalize_text(step_id)
        if normalized_step_id:
            queryset = queryset.filter(step_id=normalized_step_id)
        if axis_id is not None:
            queryset = queryset.filter(axis_id=axis_id)
        return queryset.order_by("-created_at", "-id")
