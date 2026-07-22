from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from course.models import Chapter
from exercise_bac.models import ExerciseBac
from exercise_bac.serializers import ExerciseBacSerializer


class ExerciseBacByChapterView(GenericAPIView):
    serializer_class = ExerciseBacSerializer

    def get_queryset(self):
        return (
            ExerciseBac.objects
            .select_related(
                "chapter",
            )
            .filter(
                is_active=True,
            )
            .order_by(
                "year",
                "exercise_number",
            )
        )

    def get(self, request, chapter_id):
        chapter = get_object_or_404(
            Chapter,
            id=chapter_id,
        )

        exercises = self.get_queryset().filter(
            chapter_id=chapter.id,
        )

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
                "count": exercises.count(),
                "exercises": serializer.data,
            },
            status=status.HTTP_200_OK,
        )