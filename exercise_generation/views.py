import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course.models import Axis
from exercise_generation.models import GeneratedExercise
from exercise_generation.serializers import (
    AlternativeSolutionRequestSerializer,
    ExerciseGenerationRequestSerializer,
    GeneratedExerciseAlternativeSolutionSerializer,
    GeneratedExerciseSerializer,
)
from exercise_generation.services.alternative_solution_service import (
    AlternativeSolutionGenerationError,
    AlternativeSolutionParsingError,
    AlternativeSolutionService,
)
from exercise_generation.services.exceptions import (
    AxisNotFoundError,
    EmptyAxisContentError,
    ExerciseGenerationError,
    ExerciseParsingError,
    ExerciseValidationError,
)
from exercise_generation.services.services import (
    ExerciseGenerationService,
    NoBacReferenceQuestionsError,
)

logger = logging.getLogger(__name__)


class ExerciseGenerateAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExerciseGenerationRequestSerializer

    @extend_schema(
        request=ExerciseGenerationRequestSerializer,
        responses={201: GeneratedExerciseSerializer(many=True)},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            exercises = ExerciseGenerationService().generate(
                axis_id=data["axis_id"],
                count=data["count"],
                save_to_database=data["save_to_database"],
                student=request.user,
            )
            return Response(
                {
                    "success": True,
                    "axis_id": data["axis_id"],
                    "generation_mode": "bac_like_axis_only_simple_complete_solution",
                    "requested_count": data["count"],
                    "generated_count": len(exercises),
                    "exercises": GeneratedExerciseSerializer(
                        exercises,
                        many=True,
                        context={"request": request},
                    ).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except AxisNotFoundError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (EmptyAxisContentError, NoBacReferenceQuestionsError) as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ExerciseValidationError as exc:
            return Response(
                {
                    "success": False,
                    "error": str(exc),
                    "details": exc.errors,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except (ExerciseParsingError, ExerciseGenerationError) as exc:
            logger.exception("Exercise generation failed")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class AxisGeneratedExercisesAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GeneratedExerciseSerializer

    def get(self, request, axis_id):
        axis = get_object_or_404(Axis, id=axis_id, is_active=True)
        exercises = (
            GeneratedExercise.objects.filter(
                axis=axis,
                student=request.user,
                is_active=True,
            )
            .prefetch_related("alternative_solutions")
            .order_by("-created_at")
        )
        return Response(
            {
                "axis": {"id": axis.id, "title": axis.title, "tag": axis.tag},
                "count": exercises.count(),
                "exercises": self.get_serializer(exercises, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class ExerciseAlternativeSolutionAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AlternativeSolutionRequestSerializer

    @extend_schema(
        request=AlternativeSolutionRequestSerializer,
        responses={201: GeneratedExerciseAlternativeSolutionSerializer},
    )
    def post(self, request, exercise_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        level = serializer.validated_data.get("simplification_level", "very_simple")

        exercise = get_object_or_404(
            GeneratedExercise.objects.select_related("axis", "student"),
            id=exercise_id,
            student=request.user,
            is_active=True,
        )

        try:
            alternative = AlternativeSolutionService().generate_and_save(
                exercise=exercise,
                student=request.user,
                simplification_level=level,
            )
            return Response(
                {
                    "success": True,
                    "message": "تم إنشاء حل بديل أبسط مع الاحتفاظ بالحل الأول.",
                    "exercise": {"id": exercise.id, "title": exercise.title},
                    "alternative_solution": (
                        GeneratedExerciseAlternativeSolutionSerializer(alternative).data
                    ),
                },
                status=status.HTTP_201_CREATED,
            )
        except (AlternativeSolutionParsingError, AlternativeSolutionGenerationError) as exc:
            logger.exception("Alternative solution failed")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    def get(self, request, exercise_id):
        exercise = get_object_or_404(
            GeneratedExercise,
            id=exercise_id,
            student=request.user,
            is_active=True,
        )
        alternatives = exercise.alternative_solutions.filter(
            student=request.user
        ).order_by("-created_at")
        return Response(
            {
                "success": True,
                "exercise": {"id": exercise.id, "title": exercise.title},
                "count": alternatives.count(),
                "alternative_solutions": (
                    GeneratedExerciseAlternativeSolutionSerializer(
                        alternatives,
                        many=True,
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )
