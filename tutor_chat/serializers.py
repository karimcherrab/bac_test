from rest_framework import serializers

from course.models import Axis, Chapter

from .models import StudentMessage, StudentSession


class PageContextSerializer(serializers.Serializer):
    axis_id = serializers.IntegerField(required=False, allow_null=True)
    axis_tag = serializers.CharField(required=False, allow_blank=True, max_length=120)
    axis_title = serializers.CharField(required=False, allow_blank=True, max_length=255)

    section_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    section_title = serializers.CharField(required=False, allow_blank=True, max_length=255)

    exercise = serializers.JSONField(required=False, allow_null=True)
    question = serializers.JSONField(required=False, allow_null=True)
    step = serializers.JSONField(required=False, allow_null=True)
    view_state = serializers.JSONField(required=False, default=dict)

    selection = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    visible_block = serializers.CharField(required=False, allow_blank=True, max_length=6000)

    @staticmethod
    def _validate_object(value, field_name):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                f"{field_name} يجب أن يكون كائن JSON."
            )
        return value

    def validate_exercise(self, value):
        return self._validate_object(value, "exercise")

    def validate_question(self, value):
        return self._validate_object(value, "question")

    def validate_step(self, value):
        return self._validate_object(value, "step")

    def validate_view_state(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "view_state يجب أن يكون كائن JSON."
            )
        return value


class TutorChatRequestSerializer(serializers.Serializer):
    chapter_id = serializers.PrimaryKeyRelatedField(
        queryset=Chapter.objects.filter(is_active=True),
        source="chapter",
        write_only=True,
    )

    question = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
    )

    session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    page_context = PageContextSerializer(
        required=False,
        default=dict,
    )

    def validate_question(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("اكتب سؤالًا واضحًا.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        chapter = attrs["chapter"]
        page_context = attrs.get("page_context") or {}

        axis_id = page_context.get("axis_id")
        if axis_id:
            valid_axis = Axis.objects.filter(
                id=axis_id,
                chapter=chapter,
                is_active=True,
            ).exists()
            if not valid_axis:
                raise serializers.ValidationError({
                    "page_context": "المحور لا ينتمي إلى الفصل الحالي."
                })

        session_id = attrs.get("session_id")
        if not session_id:
            return attrs

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError({
                "session_id": "يجب تسجيل الدخول لاستعمال جلسة سابقة."
            })

        student = _get_student(request.user)
        if student is None:
            raise serializers.ValidationError({
                "session_id": "لم يتم العثور على حساب الطالب."
            })

        session = (
            StudentSession.objects
            .select_related("chapter", "current_axis")
            .filter(
                id=session_id,
                student=student,
                chapter=chapter,
            )
            .first()
        )

        if session is None:
            raise serializers.ValidationError({
                "session_id": "الجلسة غير موجودة أو لا تخص هذا الطالب."
            })

        attrs["session"] = session
        return attrs


class StudentMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentMessage
        fields = (
            "id",
            "role",
            "content",
            "intent",
            "mode",
            "context_snapshot",
            "metadata",
            "created_at",
        )


class StudentSessionSerializer(serializers.ModelSerializer):
    messages = StudentMessageSerializer(many=True, read_only=True)
    chapter_title = serializers.CharField(source="chapter.title", read_only=True)
    chapter_code = serializers.CharField(source="chapter.code", read_only=True)
    axis_id = serializers.IntegerField(
        source="current_axis_id",
        read_only=True,
        allow_null=True,
    )
    axis_title = serializers.CharField(
        source="current_axis.title",
        read_only=True,
        default="",
    )
    axis_tag = serializers.CharField(
        source="current_axis.tag",
        read_only=True,
        default="",
    )

    class Meta:
        model = StudentSession
        fields = (
            "id",
            "title",
            "chapter",
            "chapter_title",
            "chapter_code",
            "axis_id",
            "axis_title",
            "axis_tag",
            "current_section",
            "current_exercise_kind",
            "current_exercise_id",
            "current_exercise_title",
            "current_question_id",
            "current_question_number",
            "current_question_title",
            "current_step_id",
            "current_step_title",
            "current_step_type",
            "current_skill",
            "current_intent",
            "last_question",
            "last_answer",
            "context_snapshot",
            "metadata",
            "is_active",
            "created_at",
            "updated_at",
            "messages",
        )


def _get_student(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if user.__class__.__name__ == "Student":
        return user
    return getattr(user, "student", None)
