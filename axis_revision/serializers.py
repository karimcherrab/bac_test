from rest_framework import serializers

from .models import AxisRevision


class AxisRevisionSerializer(
    serializers.ModelSerializer
):
    axis_id = serializers.IntegerField(
        source="axis.id",
        read_only=True,
    )

    axis_tag = serializers.CharField(
        source="axis.tag",
        read_only=True,
    )

    axis_title = serializers.CharField(
        source="axis.title",
        read_only=True,
    )

    chapter_id = serializers.IntegerField(
        source="axis.chapter.id",
        read_only=True,
    )

    chapter_code = serializers.CharField(
        source="axis.chapter.code",
        read_only=True,
    )

    class Meta:
        model = AxisRevision

        fields = [
            "id",
            "axis_id",
            "axis_tag",
            "axis_title",
            "chapter_id",
            "chapter_code",
            "tag",
            "title",
            "subtitle",
            "schema_version",
            "language",
            "direction",
            "math_format",
            "status",
            "order",
            "is_active",
            "content",
            "created_at",
            "updated_at",
        ]