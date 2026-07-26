from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course.models import (
    Branch,
    Chapter,
)
from exercise_bac.models import ExerciseBac
from exercise_bac.serializers import (
    ExerciseBacSerializer,
)


class ExerciseBacByChapterView(
    GenericAPIView
):
    serializer_class = ExerciseBacSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    def get_queryset(self):
        return (
            ExerciseBac.objects
            .select_related(
                "chapter",
                "chapter__subject",
            )
            .prefetch_related(
                "branches",
            )
            .filter(
                is_active=True,
            )
            .order_by(
                "year",
                "exercise_number",
                "id",
            )
        )

    def get(
        self,
        request,
        chapter_id,
    ):
        chapter = get_object_or_404(
            Chapter.objects.select_related(
                "subject",
            ),
            id=chapter_id,
        )

        branch_code = (
            request.query_params
            .get(
                "branch_code",
                "",
            )
            .strip()
            .lower()
        )

        exercises = (
            self.get_queryset()
            .filter(
                chapter_id=chapter.id,
            )
        )

        selected_branch = None

        if branch_code:
            selected_branch = get_object_or_404(
                Branch,
                code=branch_code,
            )

            exercises = exercises.filter(
                branches__code=branch_code,
            )

        exercises = exercises.distinct()

        serializer = self.get_serializer(
            exercises,
            many=True,
        )

        return Response(
            {
                "chapter": {
                    "id": chapter.id,
                    "code": chapter.code,
                    "title": chapter.title,
                },
                "branch": (
                    {
                        "id": selected_branch.id,
                        "code": selected_branch.code,
                        "name": selected_branch.name,
                    }
                    if selected_branch
                    else None
                ),
                "filters": {
                    "branch_code": (
                        branch_code or None
                    ),
                },
                "count": exercises.count(),
                "exercises": serializer.data,
            },
            status=status.HTTP_200_OK,
        )