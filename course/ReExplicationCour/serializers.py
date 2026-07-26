from rest_framework import serializers

from course.models import ReExplainStepHistory


class ReExplainStepRequestSerializer(serializers.Serializer):
    REQUEST_TYPES = (
        ("explanation", "شرح مبسط ومفصل"),
        ("example", "مثال توضيحي"),
    )

    step = serializers.JSONField()
    student_question = serializers.CharField(
        max_length=700,
        trim_whitespace=True,
    )
    request_type = serializers.ChoiceField(choices=REQUEST_TYPES)
    axis_id = serializers.IntegerField(min_value=1)

    def validate_step(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("المرحلة يجب أن تكون JSON Object.")

        step_id = str(value.get("id") or "").strip()
        title = str(value.get("title") or "").strip()
        content = value.get("content")

        if not step_id:
            raise serializers.ValidationError("معرف المرحلة step.id غير موجود.")
        if not title:
            raise serializers.ValidationError("عنوان المرحلة غير موجود.")
        if not isinstance(content, dict) or not content:
            raise serializers.ValidationError(
                "محتوى المرحلة يجب أن يكون JSON Object غير فارغ."
            )

        return {**value, "id": step_id, "title": title}

    def validate_student_question(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("طلب المساعدة غير صالح.")
        return value


class ReExplainGraphPointSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()
    n = serializers.IntegerField(required=False, min_value=0)
    label = serializers.CharField(required=False, allow_blank=True, max_length=40)


class ReExplainGraphSeriesSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=50)
    label = serializers.CharField(required=False, allow_blank=True, max_length=80)
    type = serializers.ChoiceField(choices=("points", "line"))
    data = ReExplainGraphPointSerializer(many=True, min_length=1, max_length=40)


class ReExplainGraphSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    x_label = serializers.CharField(max_length=40)
    y_label = serializers.CharField(max_length=40)
    x_domain = serializers.ListField(
        child=serializers.FloatField(),
        min_length=2,
        max_length=2,
    )
    y_domain = serializers.ListField(
        child=serializers.FloatField(),
        min_length=2,
        max_length=2,
    )
    series = ReExplainGraphSeriesSerializer(many=True, min_length=1, max_length=2)
    annotations = serializers.ListField(required=False, default=list)
    settings = serializers.DictField(required=False, default=dict)


class ReExplainStepAnswerSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=("explanation", "example"))
    content = serializers.CharField(allow_blank=False, max_length=4000)
    graph = ReExplainGraphSerializer(required=False, allow_null=True)


class ReExplainStepHistorySerializer(serializers.ModelSerializer):
    model = serializers.CharField(source="model_name", read_only=True)

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


class ReExplainStepResponseSerializer(serializers.Serializer):
    mode = serializers.CharField()
    step_id = serializers.CharField()
    step_title = serializers.CharField()
    model = serializers.CharField(allow_blank=True)
    answer = ReExplainStepAnswerSerializer()
    replaced_oldest = serializers.BooleanField()
    explanations_count = serializers.IntegerField()
    max_explanations = serializers.IntegerField()
    saved_explanation = ReExplainStepHistorySerializer()


class ReExplainStepHistoryListResponseSerializer(serializers.Serializer):
    step_id = serializers.CharField(allow_blank=True)
    axis_id = serializers.IntegerField(allow_null=True)
    count = serializers.IntegerField()
    max_explanations = serializers.IntegerField()
    results = ReExplainStepHistorySerializer(many=True)
