from rest_framework.serializers import ModelSerializer

from course.models import Chapter, Axis
from .models import   StudentMessage , StudentSession


class chapterSerializer(ModelSerializer):
    class Meta:
        model = Chapter
        fields = '__all__'



class axisSerializer(ModelSerializer):
    class Meta:
        model = Axis
        fields = '__all__'

# class knowledgeItemSerializer(ModelSerializer):
#     class Meta:
#         model = Axis
#         fields = '__all__'

from rest_framework import serializers

# class TutorRequestSerializer(serializers.Serializer):
#     question = serializers.CharField()
#     chapter_code = serializers.CharField(required=False, default="base")
#
# class TutorResponseSerializer(serializers.Serializer):
#     session_id = serializers.CharField()
#     mode = serializers.CharField()
#     intent = serializers.CharField()
#     axis_tag = serializers.CharField(allow_blank=True, allow_null=True)
#     axis_title = serializers.CharField(allow_blank=True, allow_null=True)
#     answer = serializers.CharField()


from rest_framework import serializers


class SolveBacExerciseRequestSerializer(serializers.Serializer):
    exercise_id = serializers.CharField()


class SolveBacExerciseResponseSerializer(serializers.Serializer):
    mode = serializers.CharField()
    exercise_id = serializers.CharField()
    answer = serializers.JSONField()


# serializers.py

from rest_framework import serializers


from rest_framework import serializers


class ExplainCourRequestSerializer(serializers.Serializer):
    """
    البيانات التي يرسلها React إلى API.
    """

    axis_id = serializers.IntegerField(
        min_value=1,
        help_text="معرف المحور المراد شرحه",
    )


class ExplainCourResponseSerializer(serializers.Serializer):
    """
    شكل الاستجابة النهائية.
    """

    mode = serializers.CharField()
    axis_id = serializers.IntegerField()
    axis_tag = serializers.CharField()
    axis_title = serializers.CharField()
    chapter_title = serializers.CharField()
    model = serializers.CharField(required=False)
    answer = serializers.JSONField()


class ExplainCourErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
    details = serializers.CharField(required=False)

from rest_framework import serializers

from course.models import Chapter
from knowledge.models import (
    StudentMessage,
    StudentSession,
)


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentSession

        fields = [
            "id",
            "student",
            "title",
            "chapter",
            "current_axis",
            "last_question",
            "last_answer",
            "current_intent",
            "current_skill",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "student",
            "created_at",
            "updated_at",
        ]


class StudentMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentMessage

        fields = [
            "id",
            "session",
            "role",
            "content",
            "intent",
            "mode",
            "chapter",
            "axis",
            "metadata",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "session",
            "created_at",
        ]


class TutorChatRequestSerializer(serializers.Serializer):
    """
    Payload reçu depuis React :

    {
        "chapter_id": 1,
        "question": "ما هي عاصمة فرنسا؟",
        "session_id": null
    }
    """

    chapter_id = serializers.IntegerField(
        min_value=1,
    )

    question = serializers.CharField(
        max_length=4000,
        trim_whitespace=True,
        allow_blank=False,
    )

    session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    def validate_chapter_id(self, value):
        try:
            chapter = (
                Chapter.objects
                .select_related("subject")
                .get(
                    id=value,
                    is_active=True,
                )
            )

        except Chapter.DoesNotExist:
            raise serializers.ValidationError(
                "Le chapitre demandé n'existe pas ou n'est pas actif."
            )

        return chapter

    def validate_question(self, value):
        clean_question = str(value).strip()

        if not clean_question:
            raise serializers.ValidationError(
                "اكتب سؤالًا أو رسالة."
            )

        return clean_question

    def validate(self, attrs):
        """
        Remplace chapter_id par l'objet Chapter.

        Dans la vue, on pourra utiliser :

            chapter = data["chapter"]
        """

        chapter = attrs.pop(
            "chapter_id"
        )

        attrs["chapter"] = chapter

        return attrs


class TutorChatResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()

    session_id = serializers.UUIDField()

    mode = serializers.CharField(
        allow_blank=True,
    )

    answer = serializers.CharField()

    intent = serializers.CharField(
        allow_blank=True,
    )

    model = serializers.CharField(
        allow_blank=True,
    )

    chapter_id = serializers.IntegerField(
        allow_null=True,
        required=False,
    )

    chapter_code = serializers.CharField(
        allow_blank=True,
        required=False,
    )

    chapter_title = serializers.CharField(
        allow_blank=True,
        required=False,
    )

    axis_id = serializers.IntegerField(
        allow_null=True,
        required=False,
    )

    axis_tag = serializers.CharField(
        allow_blank=True,
        required=False,
    )

    axis_title = serializers.CharField(
        allow_blank=True,
        required=False,
    )

    sources = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
    )


class TutorChatErrorSerializer(serializers.Serializer):
    success = serializers.BooleanField(
        default=False,
    )

    error = serializers.CharField()

    details = serializers.CharField(
        required=False,
        allow_blank=True,
    )