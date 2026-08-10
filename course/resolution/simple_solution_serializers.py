from rest_framework import serializers


class QuestionSimpleSolutionRequestSerializer(serializers.Serializer):
    """
    Body اختياري. لا نرسل السؤال أو الحل من React؛ question_id يأتي من URL.
    """

    regenerate = serializers.BooleanField(
        required=False,
        default=False,
    )


class SimpleGivenItemSerializer(serializers.Serializer):
    label = serializers.CharField(allow_blank=True)
    value = serializers.CharField(allow_blank=True)
    meaning = serializers.CharField(allow_blank=True)


class SimpleSolutionStepSerializer(serializers.Serializer):
    order = serializers.IntegerField(min_value=1)
    title = serializers.CharField()
    explanation = serializers.CharField(allow_blank=True)
    formula = serializers.CharField(allow_blank=True)
    calculation = serializers.CharField(allow_blank=True)
    result = serializers.CharField(allow_blank=True)


class SimpleSolutionPayloadSerializer(serializers.Serializer):
    teacher_intro = serializers.CharField()
    what_is_given = SimpleGivenItemSerializer(many=True)
    what_is_required = serializers.CharField(allow_blank=True)
    idea = serializers.CharField(allow_blank=True)
    steps = SimpleSolutionStepSerializer(many=True)
    final_answer = serializers.CharField()
    verification = serializers.CharField(allow_blank=True)
    memory_tip = serializers.CharField(allow_blank=True)


class QuestionSimpleSolutionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    question_id = serializers.IntegerField()
    subject = serializers.CharField()
    model = serializers.CharField()
    simple_solution = SimpleSolutionPayloadSerializer()
