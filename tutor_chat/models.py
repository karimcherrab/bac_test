import uuid

from django.db import models

from accounts.models import Student
from course.models import Axis, Chapter


class StudentSession(models.Model):
    """جلسة محادثة سياقية خاصة بالطالب وبفصل دراسي واحد."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="contextual_tutor_sessions",
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="contextual_tutor_sessions",
    )

    current_axis = models.ForeignKey(
        Axis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contextual_tutor_sessions",
    )

    current_section = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    current_exercise_kind = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    current_exercise_id = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    current_exercise_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # مهم للتمارين التي تحتوي عدة أسئلة مثل BAC وGenerated BAC.
    current_question_id = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    current_question_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    current_question_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    current_step_id = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    current_step_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    current_step_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    current_skill = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    current_intent = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    last_question = models.TextField(
        blank=True,
        default="",
    )

    last_answer = models.TextField(
        blank=True,
        default="",
    )

    # آخر لقطة سياقية موثوقة استعملها المساعد.
    context_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # class Meta:
    #     db_table = "tutor_chat_sessions"
    #     ordering = ["-updated_at"]
    #     indexes = [
    #         models.Index(
    #             fields=["student", "chapter", "is_active"],
    #             name="tutor_session_active_idx",
    #         ),
    #         models.Index(
    #             fields=["student", "updated_at"],
    #             name="tutor_session_recent_idx",
    #         ),
    #     ]

    def __str__(self):
        return f"{self.student_id} - {self.chapter_id} - {self.id}"


class StudentMessage(models.Model):
    ROLE_STUDENT = "student"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"

    ROLE_CHOICES = [
        (ROLE_STUDENT, "Student"),
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_SYSTEM, "System"),
    ]

    session = models.ForeignKey(
        StudentSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        db_index=True,
    )

    content = models.TextField()

    intent = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    mode = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contextual_tutor_messages",
    )

    axis = models.ForeignKey(
        Axis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contextual_tutor_messages",
    )

    # السياق الذي كان ظاهرًا لحظة إرسال هذه الرسالة.
    context_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    # class Meta:
    #     db_table = "tutor_chat_messages"
    #     ordering = ["created_at"]
    #     indexes = [
    #         models.Index(
    #             fields=["session", "created_at"],
    #             name="tutor_message_session_idx",
    #         ),
    #         models.Index(
    #             fields=["axis", "created_at"],
    #             name="tutor_message_axis_idx",
    #         ),
    #     ]

    def __str__(self):
        return f"{self.session_id} - {self.role} - {self.id}"
