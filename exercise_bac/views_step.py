from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from exercise_bac.models import (
    BacStepReExplanation,
    ExerciseBac,
)
from exercise_bac.serializers_step import (
    BacStepReExplanationHistoryQuerySerializer,
    BacStepReExplanationHistoryResponseSerializer,
    BacStepReExplanationItemSerializer,
    BacStepReExplanationRequestSerializer,
    BacStepReExplanationResponseSerializer,
)
from exercise_bac.services.step_reexplanation_service import (
    BacStepReExplanationError,
    BacStepReExplanationService,
)


class BacStepReExplanationAPIView(
    GenericAPIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    serializer_class = (
        BacStepReExplanationRequestSerializer
    )

    MAX_HISTORY_PER_STEP = 3

    @staticmethod
    def _find_question(
        exercise: ExerciseBac,
        question_id: str,
    ):
        for question in exercise.questions:
            if not isinstance(question, dict):
                continue

            stored_id = str(
                question.get("id", "")
            )

            if stored_id == str(question_id):
                return question

        return None

    @staticmethod
    def _find_step(
        steps: list,
        step_number: int,
    ):
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            stored_number = step.get(
                "step_number",
                index + 1,
            )

            try:
                stored_number = int(
                    stored_number
                )
            except (TypeError, ValueError):
                stored_number = index + 1

            if stored_number == step_number:
                previous_step = (
                    steps[index - 1]
                    if index > 0
                    else None
                )

                return step, previous_step

        return None, None

    @classmethod
    def _get_history_queryset(
        cls,
        *,
        student,
        exercise,
        question_id,
        step_number,
    ):
        return (
            BacStepReExplanation.objects
            .filter(
                student=student,
                exercise=exercise,
                question_id=str(question_id),
                step_number=step_number,
            )
            .select_related(
                "exercise",
            )
            .order_by(
                "-created_at",
            )
        )

    @classmethod
    def _delete_old_history(
        cls,
        *,
        student,
        exercise,
        question_id,
        step_number,
    ):
        """
        الاحتفاظ بآخر 3 شروحات فقط
        لنفس الطالب ونفس الخطوة.
        """
        history_ids = list(
            cls._get_history_queryset(
                student=student,
                exercise=exercise,
                question_id=question_id,
                step_number=step_number,
            ).values_list(
                "id",
                flat=True,
            )
        )

        ids_to_delete = history_ids[
            cls.MAX_HISTORY_PER_STEP:
        ]

        if ids_to_delete:
            (
                BacStepReExplanation.objects
                .filter(
                    id__in=ids_to_delete,
                    student=student,
                )
                .delete()
            )

    def get(self, request):
        """
        جلب الشروحات المحفوظة للطالب.

        أمثلة:

        GET /api/bac/exercises/re-explain-step/
            ?exercise_id=1

        GET /api/bac/exercises/re-explain-step/
            ?exercise_id=1
            &question_id=q1

        GET /api/bac/exercises/re-explain-step/
            ?exercise_id=1
            &question_id=q1
            &step_number=2
        """
        query_serializer = (
            BacStepReExplanationHistoryQuerySerializer(
                data=request.query_params
            )
        )

        query_serializer.is_valid(
            raise_exception=True
        )

        validated = (
            query_serializer.validated_data
        )

        exercise = get_object_or_404(
            ExerciseBac.objects.all(),
            id=validated["exercise_id"],
            is_active=True,
        )

        queryset = (
            BacStepReExplanation.objects
            .filter(
                student=request.user,
                exercise=exercise,
            )
            .select_related(
                "exercise",
            )
            .order_by(
                "-created_at",
            )
        )

        question_id = validated.get(
            "question_id"
        )

        step_number = validated.get(
            "step_number"
        )

        if question_id:
            queryset = queryset.filter(
                question_id=question_id,
            )

        if step_number is not None:
            queryset = queryset.filter(
                step_number=step_number,
            )

        explanations = list(queryset)

        response_data = {
            "success": True,
            "count": len(explanations),
            "explanations": explanations,
        }

        response_serializer = (
            BacStepReExplanationHistoryResponseSerializer(
                response_data
            )
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        validated = serializer.validated_data

        exercise = get_object_or_404(
            ExerciseBac.objects.select_related(
                "chapter"
            ),
            id=validated["exercise_id"],
            is_active=True,
        )

        question_id = validated[
            "question_id"
        ]

        step_number = validated[
            "step_number"
        ]

        request_type = validated.get(
            "request_type",
            "very_simple",
        )

        force_regenerate = validated.get(
            "force_regenerate",
            False,
        )

        question = self._find_question(
            exercise,
            question_id,
        )

        if question is None:
            return Response(
                {
                    "detail": (
                        "La question demandée "
                        "n'existe pas dans cet "
                        "exercice."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        solution = question.get(
            "solution"
        )

        if not isinstance(solution, dict):
            return Response(
                {
                    "detail": (
                        "Cette question ne contient "
                        "pas de solution."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        steps = solution.get(
            "steps",
            [],
        )

        if not isinstance(steps, list):
            steps = []

        step, previous_step = self._find_step(
            steps,
            step_number,
        )

        if step is None:
            return Response(
                {
                    "detail": (
                        "L'étape demandée "
                        "n'existe pas dans "
                        "la solution."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        history_queryset = (
            self._get_history_queryset(
                student=request.user,
                exercise=exercise,
                question_id=question_id,
                step_number=step_number,
            )
        )

        existing = history_queryset.first()

        if existing and not force_regenerate:
            history = list(
                history_queryset[
                    :self.MAX_HISTORY_PER_STEP
                ]
            )

            response_data = {
                "success": True,
                "saved": True,
                "from_cache": True,
                "history_id": existing.id,
                "exercise_id": exercise.id,
                "question_id": question_id,
                "step_number": step_number,
                "request_type": (
                    existing.request_type
                ),
                "model": existing.model,
                "explanation": (
                    existing.explanation
                ),
                "created_at": (
                    existing.created_at
                ),
                "history": history,
            }

            response_serializer = (
                BacStepReExplanationResponseSerializer(
                    response_data
                )
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK,
            )

        try:
            result = (
                BacStepReExplanationService()
                .generate(
                    exercise_title=exercise.title,
                    exercise_year=exercise.year,
                    statement=exercise.statement,
                    question_text=str(
                        question.get(
                            "text",
                            "",
                        )
                    ),
                    strategy=str(
                        solution.get(
                            "strategy",
                            "",
                        )
                    ),
                    step=step,
                    previous_step=(
                        previous_step
                        if isinstance(
                            previous_step,
                            dict,
                        )
                        else None
                    ),
                )
            )

        except BacStepReExplanationError as exc:
            return Response(
                {
                    "detail": (
                        "تعذر إنشاء شرح مبسط "
                        "لهذه الخطوة."
                    ),
                    "error": str(exc),
                },
                status=(
                    status.HTTP_502_BAD_GATEWAY
                ),
            )

        step_title = str(
            step.get(
                "title",
                "",
            )
        ).strip()

        with transaction.atomic():
            saved_explanation = (
                BacStepReExplanation.objects
                .create(
                    student=request.user,
                    exercise=exercise,
                    question_id=question_id,
                    step_number=step_number,
                    step_title=step_title,
                    request_type=request_type,
                    explanation=(
                        result.explanation
                    ),
                    model=result.model,
                )
            )

            self._delete_old_history(
                student=request.user,
                exercise=exercise,
                question_id=question_id,
                step_number=step_number,
            )

        history = list(
            self._get_history_queryset(
                student=request.user,
                exercise=exercise,
                question_id=question_id,
                step_number=step_number,
            )[
                :self.MAX_HISTORY_PER_STEP
            ]
        )

        response_data = {
            "success": True,
            "saved": True,
            "from_cache": False,
            "history_id": (
                saved_explanation.id
            ),
            "exercise_id": exercise.id,
            "question_id": question_id,
            "step_number": step_number,
            "request_type": request_type,
            "model": result.model,
            "explanation": result.explanation,
            "created_at": (
                saved_explanation.created_at
            ),
            "history": history,
        }

        response_serializer = (
            BacStepReExplanationResponseSerializer(
                response_data
            )
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )