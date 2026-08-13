import uuid

from django.db import models
from pgvector.django import VectorField

from accounts.models import Student
from course.models import (
    Subject,
    Chapter,
    Axis,
)


class RagChunk(models.Model):
    """
    جزء صغير من البيانات التعليمية مخصص للبحث الدلالي.

    البيانات الأصلية تبقى في:
    - Axis
    - Question
    - ExerciseBac

    وهذا الجدول مجرد فهرس للـ AI.
    """

    SOURCE_TYPE_CHOICES = [
        ("lesson", "Lesson"),
        ("question", "Question"),
        ("solution", "Solution"),
        ("bac_exercise", "Bac Exercise"),
    ]

    source_type = models.CharField(
        max_length=30,
        choices=SOURCE_TYPE_CHOICES,
        db_index=True,
    )

    # ID للسجل الأصلي:
    # Axis.id أو Question.id أو ExerciseBac.id
    source_id = models.PositiveBigIntegerField(
        db_index=True,
    )

    # معرف الجزء داخل المصدر.
    # مثال:
    # axis_12_step_1
    # bac_2019_ex2_question_2a
    chunk_key = models.CharField(
        max_length=255,
        db_index=True,
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="rag_chunks",
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="rag_chunks",
    )

    axis = models.ForeignKey(
        Axis,
        on_delete=models.SET_NULL,
        related_name="rag_chunks",
        null=True,
        blank=True,
    )

    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # النص الذي سنبحث عن معناه
    content = models.TextField()

    # معلومات إضافية:
    # رقم السؤال، axis_tags، difficulty...
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    # سنملأه لاحقًا.
    # إذا استعملنا BGE-M3 فالبعد 1024.
    embedding = VectorField(
        dimensions=1024,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "tutor_rag_chunk"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_type",
                    "source_id",
                    "chunk_key",
                ],
                name="unique_tutor_rag_chunk",
            ),
        ]

    def __str__(self):
        return f"{self.source_type} - {self.chunk_key}"

    import uuid

    from django.db import models

    from accounts.models import Student
    from course.models import (
        Chapter,
        Axis,
    )

class TutorChatSession(models.Model):
        """
        محادثة واحدة بين الطالب وTutor AI.
        """

        id = models.UUIDField(
            primary_key=True,
            default=uuid.uuid4,
            editable=False,
        )

        student = models.ForeignKey(
            Student,
            on_delete=models.CASCADE,
            related_name="tutor_chat_sessions",
        )

        title = models.CharField(
            max_length=255,
            blank=True,
            default="",
        )

        # السياق الذي بدأ منه الطالب المحادثة
        chapter = models.ForeignKey(
            Chapter,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name="tutor_chat_sessions",
        )

        axis = models.ForeignKey(
            Axis,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name="tutor_chat_sessions",
        )

        is_active = models.BooleanField(
            default=True,
            db_index=True,
        )

        created_at = models.DateTimeField(
            auto_now_add=True,
        )

        updated_at = models.DateTimeField(
            auto_now=True,
            db_index=True,
        )

        class Meta:
            db_table = "tutor_chat_session"

            ordering = [
                "-updated_at",
            ]

            indexes = [
                models.Index(
                    fields=[
                        "student",
                        "is_active",
                        "updated_at",
                    ],
                    name="tutor_session_student_idx",
                ),
            ]

        def __str__(self):
            return (
                f"{self.student.username} - "
                f"{self.title or self.id}"
            )

class TutorChatMessage(models.Model):
        ROLE_CHOICES = [
            ("user", "User"),
            ("assistant", "Assistant"),
        ]

        session = models.ForeignKey(
            TutorChatSession,
            on_delete=models.CASCADE,
            related_name="messages",
        )

        role = models.CharField(
            max_length=20,
            choices=ROLE_CHOICES,
            db_index=True,
        )

        content = models.TextField()

        # المصادر RAG التي استعملت للإجابة
        sources = models.JSONField(
            default=list,
            blank=True,
        )

        # معلومات إضافية مستقبلًا
        metadata = models.JSONField(
            default=dict,
            blank=True,
        )

        created_at = models.DateTimeField(
            auto_now_add=True,
            db_index=True,
        )

        class Meta:
            db_table = "tutor_chat_message"

            ordering = [
                "created_at",
                "id",
            ]

            indexes = [
                models.Index(
                    fields=[
                        "session",
                        "created_at",
                    ],
                    name="tutor_message_session_idx",
                ),
            ]

        def __str__(self):
            return (
                f"{self.session_id} - "
                f"{self.role}"
            )