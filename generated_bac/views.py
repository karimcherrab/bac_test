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
    """
    يدعم حالتين:

    1. request.user نفسه Student.
    2. request.user لديه علاقة student.

    عدّل هذه الدالة فقط إذا كانت بنية الحسابات
    عندك مختلفة.
    """

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


class GenerateBacExerciseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = (
            GenerateBacExerciseRequestSerializer(
                data=request.data,
            )
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
                GeneratedBacExercise.objects
                .select_related(
                    "chapter",
                    "branch",
                ),
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
            GeneratedBacExercise.objects
            .select_related(
                "chapter",
                "branch",
            ),
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

        queryset = (
            GeneratedBacExercise.objects
            .filter(student=student)
            .select_related(
                "chapter",
                "branch",
            )
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
