from rest_framework import serializers

from course.models import Chapter
from exercise_bac.models import ExerciseBac


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = "__all__"


class ExerciseBacSerializer(serializers.ModelSerializer):
    chapter = ChapterSerializer(
        read_only=True,
    )

    statement = serializers.CharField(
        read_only=True,
    )

    questions = serializers.JSONField(
        read_only=True,
    )

    question_count = serializers.IntegerField(
        read_only=True,
    )

    has_solutions = serializers.BooleanField(
        read_only=True,
    )

    class Meta:
        model = ExerciseBac

        fields = (
            "id",
            "code",
            "chapter",
            "year",
            "exercise_number",
            "title",
            "source_page",
            "axis_tags",
            "statement",
            "questions",
            "question_count",
            "has_solutions",
            "content",
            "source_filename",
            "schema_version",
            "language",
            "direction",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields