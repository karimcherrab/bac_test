from django.db import transaction

from course.models import (
    ReExplainStepHistory,
)


class ReExplainStepHistoryService:
    MAX_EXPLANATIONS = 3

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
        step_id = str(
            step.get("id") or ""
        ).strip()

        if not step_id:
            raise ValueError(
                "معرف المرحلة غير موجود."
            )

        step_title = str(
            step.get("title")
            or generated_result.get(
                "step_title"
            )
            or "مرحلة من الدرس"
        ).strip()

        step_type = str(
            step.get("type") or ""
        ).strip()

        answer = generated_result.get(
            "answer",
            {},
        )

        if not isinstance(answer, dict):
            answer = {
                "is_related": True,
                "relation_reason": "",
                "title": step_title,
                "simple_explanation": str(
                    answer
                ),
                "example": "",
                "steps": [],
                "check_question": "",
                "expected_answer": "",
                "encouragement": "",
            }

        model_name = str(
            generated_result.get("model")
            or ""
        ).strip()

        histories = list(
            ReExplainStepHistory.objects
            .select_for_update()
            .filter(
                student=student,
                axis=axis,
                step_id=step_id,
            )
            .order_by(
                "updated_at",
                "id",
            )
        )

        common_data = {
            "step_title": step_title,
            "step_type": step_type,
            "step_data": step,
            "student_question": (
                student_question
            ),
            "answer": answer,
            "model_name": model_name,
        }

        replaced_oldest = False

        if (
            len(histories)
            < cls.MAX_EXPLANATIONS
        ):
            history = (
                ReExplainStepHistory.objects
                .create(
                    student=student,
                    axis=axis,
                    step_id=step_id,
                    **common_data,
                )
            )

        else:
            replaced_oldest = True

            history = histories[0]

            history.step_title = (
                common_data["step_title"]
            )

            history.step_type = (
                common_data["step_type"]
            )

            history.step_data = (
                common_data["step_data"]
            )

            history.student_question = (
                common_data[
                    "student_question"
                ]
            )

            history.answer = (
                common_data["answer"]
            )

            history.model_name = (
                common_data["model_name"]
            )

            history.save(
                update_fields=[
                    "step_title",
                    "step_type",
                    "step_data",
                    "student_question",
                    "answer",
                    "model_name",
                    "updated_at",
                ]
            )

        all_history_ids = list(
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
            .values_list(
                "id",
                flat=True,
            )
        )

        if (
            len(all_history_ids)
            > cls.MAX_EXPLANATIONS
        ):
            ids_to_delete = (
                all_history_ids[
                    cls.MAX_EXPLANATIONS:
                ]
            )

            ReExplainStepHistory.objects.filter(
                id__in=ids_to_delete
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
            "replaced_oldest": (
                replaced_oldest
            ),
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

        if step_id:
            queryset = queryset.filter(
                step_id=step_id,
            )

        if axis_id:
            queryset = queryset.filter(
                axis_id=axis_id,
            )

        return queryset.order_by(
            "-updated_at",
            "-id",
        )