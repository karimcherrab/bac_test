from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Student

from .models import GeneratedBacExercise
from .serializers import (
    GenerateBacExerciseRequestSerializer,
    GenerateBacSolutionRequestSerializer,
    GeneratedBacExerciseSerializer,
)
from .services.exceptions import BacGenerationError
from .services.generation_service import (
    BacExerciseGenerationService,
)


def get_authenticated_student(request) -> Student:
    if isinstance(request.user, Student):
        return request.user

    student = getattr(
        request.user,
        "student",
        None,
    )

    if student is not None:
        return student

    raise BacGenerationError(
        "لم نتمكن من تحديد حساب الطالب."
    )


def generated_queryset():
    return (
        GeneratedBacExercise.objects
        .select_related(
            "chapter",
            "branch",
        )
        .prefetch_related(
            "re_explanations",
        )
    )


class GenerateBacExerciseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GenerateBacExerciseRequestSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        try:
            student = get_authenticated_student(
                request
            )

            generated = (
                BacExerciseGenerationService()
                .generate_exercise(
                    student=student,
                    **serializer.validated_data,
                )
            )

            generated = generated_queryset().get(
                id=generated.id,
                student=student,
            )

        except BacGenerationError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": (
                        "bac_exercise_generation_failed"
                    ),
                },
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )
        except Exception:
            return Response(
                {
                    "detail": (
                        "حدث خطأ غير متوقع "
                        "أثناء إنشاء التمرين."
                    ),
                    "code": (
                        "unexpected_generation_error"
                    ),
                },
                status=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
            )

        return Response(
            GeneratedBacExerciseSerializer(
                generated
            ).data,
            status=status.HTTP_201_CREATED,
        )


class GenerateBacSolutionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(
        self,
        request,
        exercise_id,
    ):
        request_serializer = (
            GenerateBacSolutionRequestSerializer(
                data=request.data,
            )
        )
        request_serializer.is_valid(
            raise_exception=True,
        )

        try:
            student = get_authenticated_student(
                request
            )

            generated = get_object_or_404(
                generated_queryset(),
                id=exercise_id,
                student=student,
            )

            generated = (
                BacExerciseGenerationService()
                .generate_solution(
                    generated_exercise=generated,
                    regenerate=(
                        request_serializer
                        .validated_data[
                            "regenerate"
                        ]
                    ),
                )
            )

            generated = generated_queryset().get(
                id=generated.id,
                student=student,
            )

        except BacGenerationError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": (
                        "bac_solution_generation_failed"
                    ),
                },
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )
        except Exception:
            return Response(
                {
                    "detail": (
                        "حدث خطأ غير متوقع "
                        "أثناء إنشاء الحل."
                    ),
                    "code": (
                        "unexpected_solution_error"
                    ),
                },
                status=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
            )

        return Response(
            GeneratedBacExerciseSerializer(
                generated
            ).data,
            status=status.HTTP_200_OK,
        )


class ReExplainBacQuestionSolutionAPIView(APIView):
    """
    يعيد شرح حل سؤال واحد ويخزن كل محاولة في قاعدة البيانات.

    لا يعمل قبل إنشاء الحل الكامل للتمرين.
    """

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request,
        exercise_id,
        question_id,
    ):
        try:
            student = get_authenticated_student(
                request
            )

            generated = get_object_or_404(
                generated_queryset(),
                id=exercise_id,
                student=student,
            )

            BacExerciseGenerationService().re_explain_solution_question(
                generated_exercise=generated,
                student=student,
                question_id=str(question_id),
            )

            # نعيد التمرين كاملًا حتى تتحدث الواجهة مباشرة
            # ويكون re_explanations متزامنًا مع قاعدة البيانات.
            generated = generated_queryset().get(
                id=generated.id,
                student=student,
            )

        except BacGenerationError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": (
                        "bac_solution_re_explanation_failed"
                    ),
                },
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "invalid_question_solution",
                },
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )
        except Exception:
            return Response(
                {
                    "detail": (
                        "تعذر إعادة شرح الحل حاليًا."
                    ),
                    "code": (
                        "unexpected_re_explanation_error"
                    ),
                },
                status=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
            )

        return Response(
            GeneratedBacExerciseSerializer(
                generated
            ).data,
            status=status.HTTP_201_CREATED,
        )


class GeneratedBacExerciseDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(
        self,
        request,
        exercise_id,
    ):
        try:
            student = get_authenticated_student(
                request
            )
        except BacGenerationError as exc:
            return Response(
                {"detail": str(exc)},
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )

        generated = get_object_or_404(
            generated_queryset(),
            id=exercise_id,
            student=student,
        )

        return Response(
            GeneratedBacExerciseSerializer(
                generated
            ).data,
            status=status.HTTP_200_OK,
        )


class MyGeneratedBacExercisesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = get_authenticated_student(
                request
            )
        except BacGenerationError as exc:
            return Response(
                {"detail": str(exc)},
                status=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
            )

        queryset = generated_queryset().filter(
            student=student
        )

        chapter_id = request.query_params.get(
            "chapter_id",
        )
        branch_code = request.query_params.get(
            "branch_code",
        )

        if chapter_id:
            queryset = queryset.filter(
                chapter_id=chapter_id,
            )

        if branch_code:
            queryset = queryset.filter(
                branch__code=branch_code,
            )

        queryset = queryset[:30]

        return Response(
            {
                "count": len(queryset),
                "results": (
                    GeneratedBacExerciseSerializer(
                        queryset,
                        many=True,
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )
