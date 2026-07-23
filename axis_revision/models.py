from django.conf import settings
from django.db import models

from course.models import Axis


class AxisRevision(models.Model):
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("generated", "تم التوليد"),
        ("reviewed", "تمت المراجعة"),
        ("published", "منشور"),
        ("published_ready", "جاهز للنشر"),
    ]

    axis = models.OneToOneField(
        Axis,
        on_delete=models.CASCADE,
        related_name="revision",
    )

    tag = models.CharField(
        max_length=180,
        unique=True,
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
    )

    subtitle = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    schema_version = models.CharField(
        max_length=20,
        default="1.0",
    )

    language = models.CharField(
        max_length=10,
        default="ar",
    )

    direction = models.CharField(
        max_length=10,
        default="rtl",
    )

    math_format = models.CharField(
        max_length=30,
        default="LaTeX",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    # ملف الملخص كاملًا
    content = models.JSONField(
        default=dict,
        blank=True,
    )

    imported_file_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_axis_revisions",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order",
            "id",
        ]

        verbose_name = "ملخص مراجعة المحور"
        verbose_name_plural = "ملخصات مراجعة المحاور"

    def __str__(self):
        return self.title