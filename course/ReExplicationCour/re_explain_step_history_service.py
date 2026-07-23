from typing import Any

from django.db import transaction

from course.models import (
    ReExplainStepHistory,
)


class ReExplainStepHistoryService:
    """
    حفظ آخر 3 شروحات لكل:
    - تلميذ.
    - محور.
    - مرحلة.

    عند وجود 3 شروحات، يتم حذف الأقدم
    وإنشاء سجل جديد بدل تعديل السجل القديم.
    """

    MAX_EXPLANATIONS = 3

    @classmethod
    def normalize_text(
        cls,
        value: Any,
        default: str = "",
    ) -> str:
        if value is None:
            return default

        value = str(value).strip()
        return value or default

    @classmethod
    def normalize_answer(
        cls,
        answer: Any,
        step_title: str,
    ) -> dict:
        if isinstance(answer, dict):
            return answer

        return {
            "is_related": True,
            "relation_reason": "",
            "title": step_title,
            "direct_answer": cls.normalize_text(
                answer
            ),
            "simple_explanation": (
                cls.normalize_text(answer)
            ),
            "example": "",
            "steps": [],
            "check_question": "",
            "expected_answer": "",
            "encouragement": "",
        }

    @classmethod
    @transaction.atomic
    def save_history(
        cls,
        *,
        student,
        step: dict,
        axis,
        student_question: str,
        generated_result: dict,
    ) -> dict:
        if student is None:
            raise ValueError(
                "التلميذ غير موجود."
            )

        if axis is None:
            raise ValueError(
                "المحور غير موجود."
            )

        if not isinstance(step, dict):
            raise ValueError(
                "بيانات المرحلة غير صحيحة."
            )

        if not isinstance(
            generated_result,
            dict,
        ):
            raise ValueError(
                "نتيجة التوليد غير صحيحة."
            )

        step_id = cls.normalize_text(
            step.get("id")
        )

        if not step_id:
            raise ValueError(
                "معرف المرحلة غير موجود."
            )

        step_title = cls.normalize_text(
            step.get("title")
            or generated_result.get(
                "step_title"
            ),
            "مرحلة من الدرس",
        )

        step_type = cls.normalize_text(
            step.get("type")
        )

        student_question = cls.normalize_text(
            student_question
        )

        answer = cls.normalize_answer(
            answer=generated_result.get(
                "answer",
                {},
            ),
            step_title=step_title,
        )

        model_name = cls.normalize_text(
            generated_result.get("model")
        )

        base_queryset = (
            ReExplainStepHistory.objects
            .select_for_update()
            .filter(
                student=student,
                axis=axis,
                step_id=step_id,
            )
        )

        current_histories = list(
            base_queryset.order_by(
                "-updated_at",
                "-id",
            )
        )

        replaced_oldest = False

        if (
            len(current_histories)
            >= cls.MAX_EXPLANATIONS
        ):
            replaced_oldest = True

            ids_to_delete = [
                history.id
                for history
                in current_histories[
                    cls.MAX_EXPLANATIONS - 1:
                ]
            ]

            if ids_to_delete:
                ReExplainStepHistory.objects.filter(
                    id__in=ids_to_delete
                ).delete()

        history = (
            ReExplainStepHistory.objects.create(
                student=student,
                axis=axis,
                step_id=step_id,
                step_title=step_title,
                step_type=step_type,
                step_data=step,
                student_question=student_question,
                answer=answer,
                model_name=model_name,
            )
        )

        remaining_histories = (
            ReExplainStepHistory.objects
            .filter(
                student=student,
                axis=axis,
                step_id=step_id,
            )
            .order_by(
                "-updated_at",
                "-id",
            )
        )

        extra_ids = list(
            remaining_histories.values_list(
                "id",
                flat=True,
            )[cls.MAX_EXPLANATIONS:]
        )

        if extra_ids:
            ReExplainStepHistory.objects.filter(
                id__in=extra_ids
            ).delete()

        count = (
            ReExplainStepHistory.objects
            .filter(
                student=student,
                axis=axis,
                step_id=step_id,
            )
            .count()
        )

        return {
            "history": history,
            "replaced_oldest": replaced_oldest,
            "count": count,
        }

    @classmethod
    def get_student_history(
        cls,
        *,
        student,
        step_id: str | None = None,
        axis_id: int | None = None,
    ):
        queryset = (
            ReExplainStepHistory.objects
            .select_related("axis")
            .filter(
                student=student,
            )
        )

        normalized_step_id = cls.normalize_text(
            step_id
        )

        if normalized_step_id:
            queryset = queryset.filter(
                step_id=normalized_step_id,
            )

        if axis_id is not None:
            try:
                normalized_axis_id = int(
                    axis_id
                )

                queryset = queryset.filter(
                    axis_id=normalized_axis_id,
                )

            except (
                TypeError,
                ValueError,
            ):
                return queryset.none()

        return queryset.order_by(
            "-updated_at",
            "-id",
        )