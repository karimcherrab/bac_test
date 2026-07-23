from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Axis

from .models import AxisRevision
from .serializers import AxisRevisionSerializer


class AxisRevisionDetailAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        axis_id,
    ):
        try:
            revision = (
                AxisRevision.objects
                .select_related(
                    "axis",
                    "axis__chapter",
                )
                .get(
                    axis_id=axis_id,
                    is_active=True,
                )
            )

        except AxisRevision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "detail": (
                        "لا يوجد ملخص مراجعة "
                        "لهذا المحور."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AxisRevisionSerializer(
            revision,
        )

        return Response(
            {
                "success": True,
                "revision": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AxisRevisionByTagAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        axis_tag,
    ):
        try:
            revision = (
                AxisRevision.objects
                .select_related(
                    "axis",
                    "axis__chapter",
                )
                .get(
                    axis__tag=axis_tag,
                    is_active=True,
                )
            )

        except AxisRevision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "detail": (
                        "لا يوجد ملخص مراجعة "
                        "لهذا المحور."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AxisRevisionSerializer(
            revision,
        )

        return Response(
            {
                "success": True,
                "revision": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ChapterAxisRevisionListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        chapter_id,
    ):
        revisions = (
            AxisRevision.objects
            .select_related(
                "axis",
                "axis__chapter",
            )
            .filter(
                axis__chapter_id=chapter_id,
                is_active=True,
            )
            .order_by(
                "order",
                "id",
            )
        )

        serializer = AxisRevisionSerializer(
            revisions,
            many=True,
        )

        return Response(
            {
                "success": True,
                "chapter_id": chapter_id,
                "count": revisions.count(),
                "revisions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )