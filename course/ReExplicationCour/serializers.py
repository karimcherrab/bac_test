from rest_framework import serializers

from course.models import ReExplainStepHistory


class ReExplainStepRequestSerializer(serializers.Serializer):
    step = serializers.JSONField()

    student_question = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
    )

    axis_id = serializers.IntegerField(
        min_value=1,
    )

    def validate_step(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "المرحلة يجب أن تكون JSON Object."
            )

        step_id = str(
            value.get("id") or ""
        ).strip()

        if not step_id:
            raise serializers.ValidationError(
                "معرف المرحلة step.id غير موجود."
            )

        title = str(
            value.get("title") or ""
        ).strip()

        if not title:
            raise serializers.ValidationError(
                "عنوان المرحلة غير موجود."
            )

        if "content" not in value:
            raise serializers.ValidationError(
                "محتوى المرحلة غير موجود."
            )

        content = value.get("content")

        if not isinstance(content, dict):
            raise serializers.ValidationError(
                "محتوى المرحلة يجب أن يكون JSON Object."
            )

        if not content:
            raise serializers.ValidationError(
                "محتوى المرحلة فارغ."
            )

        value["id"] = step_id
        value["title"] = title

        return value

    def validate_student_question(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "اكتب السؤال الذي لم تفهمه."
            )

        return value


class ReExplainStepHistorySerializer(
    serializers.ModelSerializer
):
    model = serializers.CharField(
        source="model_name",
        read_only=True,
    )

    class Meta:
        model = ReExplainStepHistory

        fields = [
            "id",
            "step_id",
            "axis",
            "step_title",
            "step_type",
            "step_data",
            "student_question",
            "answer",
            "model",
            "model_name",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class ReExplainStepAnswerSerializer(
    serializers.Serializer
):
    is_related = serializers.BooleanField()

    relation_reason = serializers.CharField(
        allow_blank=True,
    )

    title = serializers.CharField(
        allow_blank=True,
    )

    simple_explanation = serializers.CharField(
        allow_blank=True,
    )

    example = serializers.CharField(
        allow_blank=True,
    )

    steps = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )

    check_question = serializers.CharField(
        allow_blank=True,
    )

    expected_answer = serializers.CharField(
        allow_blank=True,
    )

    encouragement = serializers.CharField(
        allow_blank=True,
    )


class ReExplainStepResponseSerializer(
    serializers.Serializer
):
    mode = serializers.CharField()

    step_id = serializers.CharField()

    step_title = serializers.CharField()

    model = serializers.CharField(
        allow_blank=True,
    )

    answer = ReExplainStepAnswerSerializer()

    replaced_oldest = serializers.BooleanField()

    explanations_count = serializers.IntegerField()

    max_explanations = serializers.IntegerField()

    saved_explanation = (
        ReExplainStepHistorySerializer()
    )


class ReExplainStepHistoryListResponseSerializer(
    serializers.Serializer
):
    step_id = serializers.CharField(
        allow_blank=True,
    )

    count = serializers.IntegerField()

    max_explanations = serializers.IntegerField()

    results = ReExplainStepHistorySerializer(
        many=True,
    )