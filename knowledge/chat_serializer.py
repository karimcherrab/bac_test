from rest_framework import serializers

from course.models import Chapter
from knowledge.models import StudentSession


class TutorChatRequestSerializer(serializers.Serializer):
    chapter_id = serializers.PrimaryKeyRelatedField(
        queryset=Chapter.objects.filter(
            is_active=True,
        ),
        source="chapter",
        write_only=True,
        help_text="Identifiant du chapitre actif.",
    )

    question = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
        help_text="Question posée par l'étudiant.",
    )

    session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text=(
            "Identifiant de la session existante. "
            "Laisser vide pour créer une nouvelle session."
        ),
    )

    def validate_question(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "اكتب سؤالًا واضحًا."
            )

        return value

    def validate(self, attrs):
        request = self.context.get("request")
        session_id = attrs.get("session_id")
        chapter = attrs["chapter"]

        if not session_id:
            return attrs

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError({
                "session_id": (
                    "يجب تسجيل الدخول لاستعمال جلسة سابقة."
                )
            })

        student = self._get_student(request.user)

        if student is None:
            raise serializers.ValidationError({
                "session_id": (
                    "لم يتم العثور على حساب الطالب المرتبط بالمستخدم."
                )
            })

        session = (
            StudentSession.objects
            .select_related(
                "student",
                "chapter",
                "current_axis",
            )
            .filter(
                id=session_id,
                student=student,
            )
            .first()
        )

        if session is None:
            raise serializers.ValidationError({
                "session_id": (
                    "الجلسة غير موجودة أو لا تخص هذا الطالب."
                )
            })

        if (
            session.chapter_id
            and session.chapter_id != chapter.id
        ):
            raise serializers.ValidationError({
                "chapter_id": (
                    "هذه الجلسة مرتبطة بفصل آخر. "
                    "أنشئ جلسة جديدة لهذا الفصل."
                )
            })

        attrs["session"] = session

        return attrs

    @staticmethod
    def _get_student(user):
        """
        Adapte cette méthode selon ta structure.

        Cas 1 :
        request.user est directement Student.

        Cas 2 :
        request.user possède une relation student.
        """

        if user.__class__.__name__ == "Student":
            return user

        return getattr(user, "student", None)


class TutorSourceSerializer(serializers.Serializer):
    type = serializers.CharField()

    id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    tag = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    title = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    year = serializers.IntegerField(
        required=False,
        allow_null=True,
    )


class TutorChatResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()

    session_id = serializers.UUIDField()

    mode = serializers.CharField()
    answer = serializers.CharField()
    intent = serializers.CharField()
    model = serializers.CharField()

    chapter_id = serializers.IntegerField()
    chapter_code = serializers.CharField(
        allow_blank=True,
    )
    chapter_title = serializers.CharField(
        allow_blank=True,
    )

    axis_id = serializers.IntegerField(
        allow_null=True,
    )
    axis_tag = serializers.CharField(
        allow_blank=True,
    )
    axis_title = serializers.CharField(
        allow_blank=True,
    )

    sources = TutorSourceSerializer(
        many=True,
        required=False,
    )


class TutorChatErrorSerializer(serializers.Serializer):
    success = serializers.BooleanField(
        default=False,
    )

    error = serializers.CharField()

    details = serializers.JSONField(
        required=False,
    )