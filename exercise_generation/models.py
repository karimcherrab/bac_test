from django.db import models

from accounts.models import Student
from course.models import Axis


class GeneratedExercise(models.Model):
    DIFFICULTY_CHOICES = [
        ("easy", "سهل"),
        ("medium", "متوسط"),
        ("hard", "صعب"),
    ]

    axis = models.ForeignKey(
        Axis,
        on_delete=models.CASCADE,
        related_name="generated_exercises",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="generated_exercises",
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    question = models.TextField()

    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
    )

    exercise_type = models.CharField(
        max_length=100,
        default="application",
    )

    skill = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    hints = models.JSONField(
        default=list,
        blank=True,
    )

    solution_steps = models.JSONField(
        default=list,
        blank=True,
    )

    final_answer = models.TextField(
        blank=True,
        default="",
    )

    common_mistake = models.TextField(
        blank=True,
        default="",
    )

    model_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    raw_ai_response = models.JSONField(
        default=dict,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    requires_graph = models.BooleanField(
        default=False,
    )

    graph_data = models.JSONField(
        default=dict,
        blank=True,
    )

    verification = models.TextField(
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class GeneratedExerciseAlternativeSolution(models.Model):
    """
    حل إضافي أبسط يطلبه التلميذ بعد مشاهدة الحل الأول.

    لا يتم تعديل الحل الأصلي الموجود داخل GeneratedExercise.
    """

    exercise = models.ForeignKey(
        GeneratedExercise,
        on_delete=models.CASCADE,
        related_name="alternative_solutions",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="generated_exercise_alternative_solutions",
    )

    explanation = models.TextField(
        blank=True,
        default="",
    )

    solution_steps = models.JSONField(
        default=list,
        blank=True,
    )

    final_answer = models.TextField(
        blank=True,
        default="",
    )

    model_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    raw_ai_response = models.JSONField(
        default=dict,
        blank=True,
    )



    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "حل بديل مبسط"
        verbose_name_plural = "الحلول البديلة المبسطة"

    def __str__(self):
        return f"حل مبسط - {self.exercise.title}"





