from rest_framework import serializers

from exercise_bac.models import (
    BacStepReExplanation,
)


class BacStepReExplanationRequestSerializer(
    serializers.Serializer
):
    exercise_id = serializers.IntegerField(
        min_value=1,
    )

    question_id = serializers.CharField(
        max_length=150,
    )

    step_number = serializers.IntegerField(
        min_value=1,
    )

    request_type = serializers.ChoiceField(
        choices=[
            "very_simple",
        ],
        default="very_simple",
        required=False,
    )

    force_regenerate = serializers.BooleanField(
        default=False,
        required=False,
        help_text=(
            "إذا كانت true يتم إنشاء شرح جديد "
            "حتى لو وُجد شرح محفوظ."
        ),
    )

    def validate_question_id(self, value):
        value = str(value).strip()

        if not value:
            raise serializers.ValidationError(
                "question_id est obligatoire."
            )

        return value


class BacStepReExplanationHistoryQuerySerializer(
    serializers.Serializer
):
    exercise_id = serializers.IntegerField(
        min_value=1,
    )

    question_id = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=False,
    )

    step_number = serializers.IntegerField(
        min_value=1,
        required=False,
    )

    def validate_question_id(self, value):
        return str(value).strip()


class BacStepReExplanationItemSerializer(
    serializers.ModelSerializer
):
    exercise_id = serializers.IntegerField(
        source="exercise.id",
        read_only=True,
    )

    exercise_title = serializers.CharField(
        source="exercise.title",
        read_only=True,
    )

    class Meta:
        model = BacStepReExplanation

        fields = [
            "id",
            "exercise_id",
            "exercise_title",
            "question_id",
            "step_number",
            "step_title",
            "request_type",
            "model",
            "explanation",
            "created_at",
            "updated_at",
        ]


class BacStepReExplanationResponseSerializer(
    serializers.Serializer
):
    success = serializers.BooleanField()

    saved = serializers.BooleanField()

    from_cache = serializers.BooleanField()

    history_id = serializers.IntegerField()

    exercise_id = serializers.IntegerField()

    question_id = serializers.CharField()

    step_number = serializers.IntegerField()

    request_type = serializers.CharField()

    model = serializers.CharField()

    explanation = serializers.JSONField()

    created_at = serializers.DateTimeField()

    history = (
        BacStepReExplanationItemSerializer(
            many=True,
        )
    )


class BacStepReExplanationHistoryResponseSerializer(
    serializers.Serializer
):
    success = serializers.BooleanField()

    count = serializers.IntegerField()

    explanations = (
        BacStepReExplanationItemSerializer(
            many=True,
        )
    )