import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from accounts.models import Student
from course.models import Subject, Chapter


class Pack(models.Model):
    class PackType(models.TextChoices):
        CHAPTER = "chapter", "Chapter"
        SUBJECT = "subject", "Subject"

    pack_type = models.CharField(max_length=20, choices=PackType.choices, db_index=True)
    name = models.CharField(max_length=255)
    chapter = models.ForeignKey(
        Chapter, on_delete=models.PROTECT, related_name="payment_packs",
        null=True, blank=True,
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="payment_packs",
        null=True, blank=True,
    )
    price_dzd = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pack_type", "price_dzd", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(pack_type="chapter", chapter__isnull=False, subject__isnull=True)
                    |
                    Q(pack_type="subject", subject__isnull=False, chapter__isnull=True)
                ),
                name="pack_has_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["chapter"],
                condition=Q(pack_type="chapter"),
                name="unique_pack_per_chapter",
            ),
            models.UniqueConstraint(
                fields=["subject"],
                condition=Q(pack_type="subject"),
                name="unique_pack_per_subject",
            ),
        ]

    def clean(self):
        super().clean()
        if self.pack_type == self.PackType.CHAPTER:
            if not self.chapter:
                raise ValidationError({"chapter": "Chapter pack requires chapter."})
            if self.subject:
                raise ValidationError({"subject": "Chapter pack cannot have subject."})
        elif self.pack_type == self.PackType.SUBJECT:
            if not self.subject:
                raise ValidationError({"subject": "Subject pack requires subject."})
            if self.chapter:
                raise ValidationError({"chapter": "Subject pack cannot have chapter."})

    @property
    def target_title(self):
        if self.pack_type == self.PackType.CHAPTER:
            return self.chapter.title if self.chapter else ""
        return self.subject.name if self.subject else ""

    def __str__(self):
        return f"{self.name} - {self.price_dzd} DZD"


class ChargilyCustomerLink(models.Model):
    class Environment(models.TextChoices):
        TEST = "test", "Test"
        LIVE = "live", "Live"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="chargily_customer_links",
    )
    environment = models.CharField(
        max_length=10,
        choices=Environment.choices,
        db_index=True,
    )
    customer_id = models.CharField(max_length=150)
    email_snapshot = models.EmailField(blank=True, default="")
    name_snapshot = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_id", "environment"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "environment"],
                name="unique_student_chargily_environment",
            ),
            models.UniqueConstraint(
                fields=["environment", "customer_id"],
                name="unique_chargily_customer_per_environment",
            ),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.environment} - {self.customer_id}"


class Purchase(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        ERROR = "error", "Error"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="purchases"
    )
    pack = models.ForeignKey(
        Pack, on_delete=models.PROTECT, related_name="purchases"
    )
    amount_dzd = models.PositiveIntegerField()
    currency = models.CharField(max_length=10, default="dzd")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    chargily_checkout_id = models.CharField(
        max_length=150, unique=True, null=True, blank=True
    )
    chargily_customer_id = models.CharField(max_length=150, blank=True, default="")
    customer_email = models.EmailField(blank=True, default="")
    checkout_url = models.URLField(max_length=1000, blank=True, default="")
    payment_method = models.CharField(max_length=50, blank=True, default="")
    provider_data = models.JSONField(default=dict, blank=True)
    webhook_data = models.JSONField(default=dict, blank=True)
    provider_error = models.TextField(blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["student", "status"],
                name="purchase_student_status_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "pack"],
                condition=Q(status="pending"),
                name="one_pending_purchase_per_pack",
            ),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.pack_id} - {self.status}"


class StudentAccess(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="paid_accesses"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="student_accesses",
        null=True, blank=True,
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.PROTECT, related_name="student_accesses",
        null=True, blank=True,
    )
    source_purchase = models.ForeignKey(
        Purchase, on_delete=models.SET_NULL, related_name="access_grants",
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(subject__isnull=False, chapter__isnull=True)
                    |
                    Q(subject__isnull=True, chapter__isnull=False)
                ),
                name="access_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["student", "subject"],
                condition=Q(subject__isnull=False),
                name="unique_student_subject_access",
            ),
            models.UniqueConstraint(
                fields=["student", "chapter"],
                condition=Q(chapter__isnull=False),
                name="unique_student_chapter_access",
            ),
        ]

    def __str__(self):
        if self.subject_id:
            return f"{self.student_id} -> Subject {self.subject_id}"
        return f"{self.student_id} -> Chapter {self.chapter_id}"
