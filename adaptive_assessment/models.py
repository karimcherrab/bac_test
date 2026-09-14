from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Branch, Student
from course.models import Axis


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Skill(TimeStampedModel):
    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    axis = models.ForeignKey(
        Axis,
        on_delete=models.CASCADE,
        related_name="assessment_skills",
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    # Keeps SkillIdea data without creating another table.
    # Expected item:
    # {
    #   "code": "...",
    #   "name": "...",
    #   "difficulty": "easy|medium|hard",
    #   "source": "axis_lesson"
    # }
    ideas = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["axis_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["axis", "code"],
                name="adaptive_unique_skill_code_per_axis",
            )
        ]
        indexes = [
            models.Index(fields=["axis", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def idea_codes(self):
        return [
            item.get("code")
            for item in (self.ideas or [])
            if isinstance(item, dict) and item.get("code")
        ]


class BacIdea(TimeStampedModel):
    PRIORITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    FREQUENCY_CHOICES = [
        ("very_high", "Very high"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("rare", "Rare"),
    ]

    axis = models.ForeignKey(
        Axis,
        on_delete=models.CASCADE,
        related_name="bac_ideas",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="bac_ideas",
    )

    code = models.CharField(max_length=120)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="medium",
    )
    frequency_level = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="medium",
    )

    occurrence_count = models.PositiveIntegerField(default=0)
    years = models.JSONField(default=list, blank=True)

    # References from the BAC JSON.
    required_skills = models.JSONField(default=list, blank=True)
    prerequisites = models.JSONField(default=list, blank=True)
    external_prerequisites = models.JSONField(default=list, blank=True)

    difficulty_min = models.PositiveSmallIntegerField(default=1)
    difficulty_max = models.PositiveSmallIntegerField(default=3)

    # Stores the BAC source occurrences and avoids a separate table.
    bac_occurrences = models.JSONField(default=list, blank=True)

    mastery_requirements = models.JSONField(default=dict, blank=True)
    generation_guidance = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["axis_id", "branch_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["axis", "branch", "code"],
                name="adaptive_unique_bac_idea_axis_branch_code",
            )
        ]
        indexes = [
            models.Index(fields=["axis", "branch", "is_active"]),
            models.Index(fields=["priority", "frequency_level"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def clean(self):
        if self.difficulty_min < 1 or self.difficulty_max > 5:
            raise ValidationError("BAC idea difficulty must be between 1 and 5.")
        if self.difficulty_min > self.difficulty_max:
            raise ValidationError("difficulty_min cannot exceed difficulty_max.")


class BacIdeaVariant(TimeStampedModel):
    bac_idea = models.ForeignKey(
        BacIdea,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    code = models.CharField(max_length=140)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    years = models.JSONField(default=list, blank=True)
    occurrence_count = models.PositiveIntegerField(default=0)
    difficulty = models.PositiveSmallIntegerField(default=1)
    required_skills = models.JSONField(default=list, blank=True)
    distinguishing_feature = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["bac_idea_id", "difficulty", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["bac_idea", "code"],
                name="adaptive_unique_variant_code_per_bac_idea",
            )
        ]
        indexes = [
            models.Index(fields=["bac_idea", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.bac_idea.code}/{self.code}"

    def clean(self):
        if not 1 <= self.difficulty <= 5:
            raise ValidationError("Variant difficulty must be between 1 and 5.")


class Misconception(TimeStampedModel):
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    axis = models.ForeignKey(
        Axis,
        on_delete=models.CASCADE,
        related_name="misconceptions",
    )
    code = models.CharField(max_length=140)
    description = models.TextField()
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="medium",
    )

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="misconceptions",
        null=True,
        blank=True,
    )
    bac_idea = models.ForeignKey(
        BacIdea,
        on_delete=models.CASCADE,
        related_name="misconceptions",
        null=True,
        blank=True,
    )

    related_skill_idea_codes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["axis_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["axis", "code"],
                name="adaptive_unique_misconception_code_per_axis",
            )
        ]
        indexes = [
            models.Index(fields=["axis", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def clean(self):
        if not self.skill_id and not self.bac_idea_id:
            raise ValidationError(
                "A misconception must belong to a Skill or BacIdea."
            )
        if self.skill_id and self.skill.axis_id != self.axis_id:
            raise ValidationError("Skill and misconception must share the same axis.")
        if self.bac_idea_id and self.bac_idea.axis_id != self.axis_id:
            raise ValidationError("BacIdea and misconception must share the same axis.")

    def __str__(self):
        return f"{self.code} - {self.description[:60]}"


class StudentSkillMastery(TimeStampedModel):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="skill_masteries",
    null=True,
    blank=True,
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="student_masteries",
    )

    mastery_score = models.FloatField(default=0.0)
    attempts_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    consecutive_successes = models.PositiveIntegerField(default=0)
    mastered_idea_codes = models.JSONField(default=list, blank=True)
    weak_idea_codes = models.JSONField(default=list, blank=True)
    is_mastered = models.BooleanField(default=False)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "skill"],
                name="adaptive_unique_student_skill_mastery",
            )
        ]
        indexes = [
            models.Index(fields=["student", "is_mastered"]),
            models.Index(fields=["skill", "mastery_score"]),
        ]

    def __str__(self):
        return f"{self.student_id}/{self.skill.code}: {self.mastery_score:.2f}"


class StudentBacIdeaMastery(TimeStampedModel):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="bac_idea_masteries",
    null=True,
    blank=True,
    )
    bac_idea = models.ForeignKey(
        BacIdea,
        on_delete=models.CASCADE,
        related_name="student_masteries",
    )

    mastery_score = models.FloatField(default=0.0)
    attempts_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    consecutive_successes = models.PositiveIntegerField(default=0)

    mastered_variant_codes = models.JSONField(default=list, blank=True)
    weak_variant_codes = models.JSONField(default=list, blank=True)
    detected_misconception_codes = models.JSONField(default=list, blank=True)

    is_mastered = models.BooleanField(default=False)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "bac_idea"],
                name="adaptive_unique_student_bac_idea_mastery",
            )
        ]
        indexes = [
            models.Index(fields=["student", "is_mastered"]),
            models.Index(fields=["bac_idea", "mastery_score"]),
        ]

    def __str__(self):
        return f"{self.student_id}/{self.bac_idea.code}: {self.mastery_score:.2f}"


class AdaptiveTest(TimeStampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    MODE_CHOICES = [
        ("full", "Full axis assessment"),
        ("remedial", "Weak-points retest"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="adaptive_tests",
    null=True,
    blank=True,
    )
    axis = models.ForeignKey(
        Axis,
        on_delete=models.CASCADE,
        related_name="adaptive_tests",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="adaptive_tests",
        null=True,
        blank=True,
    )

    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="full")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    blueprint = models.JSONField(default=dict, blank=True)
    score = models.FloatField(null=True, blank=True)
    mastery_score = models.FloatField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # class Meta:
    #     ordering = ["-created_at"]
    #     indexes = [
    #         models.Index(fields=["student", "axis", "status"]),
    #         models.Index(fields=["student", "created_at"]),
    #     ]

    def mark_started(self):
        if not self.started_at:
            self.started_at = timezone.now()
        self.status = "in_progress"
        self.save(update_fields=["started_at", "status", "updated_at"])

    def __str__(self):
        return f"Test #{self.pk} - {self.student_id} - {self.axis_id}"


class AdaptiveTestQuestion(TimeStampedModel):
    SOURCE_CHOICES = [
        ("bac", "BAC idea"),
        ("skill", "Lesson skill"),
    ]

    test = models.ForeignKey(
        AdaptiveTest,
        on_delete=models.CASCADE,
        related_name="test_questions",
    )
    order = models.PositiveIntegerField()

    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        related_name="test_questions",
        null=True,
        blank=True,
    )
    bac_idea = models.ForeignKey(
        BacIdea,
        on_delete=models.SET_NULL,
        related_name="test_questions",
        null=True,
        blank=True,
    )
    variant = models.ForeignKey(
        BacIdeaVariant,
        on_delete=models.SET_NULL,
        related_name="test_questions",
        null=True,
        blank=True,
    )

    target_skill_idea_codes = models.JSONField(default=list, blank=True)
    target_misconception_codes = models.JSONField(default=list, blank=True)

    difficulty = models.PositiveSmallIntegerField(default=1)

    # Generated and validated question payload:
    # statement, answer_type, choices, correct_answer, solution,
    # grading_rubric, validator metadata...
    question = models.JSONField(default=dict)

    generation_model = models.CharField(max_length=120, blank=True, default="")
    validation_report = models.JSONField(default=dict, blank=True)
    is_validated = models.BooleanField(default=False)

    class Meta:
        ordering = ["test_id", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["test", "order"],
                name="adaptive_unique_question_order_per_test",
            )
        ]
        indexes = [
            models.Index(fields=["test", "order"]),
            models.Index(fields=["bac_idea", "variant"]),
            models.Index(fields=["skill"]),
        ]

    def clean(self):
        if self.source_type == "bac" and not self.bac_idea_id:
            raise ValidationError("BAC question requires bac_idea.")
        if self.source_type == "skill" and not self.skill_id:
            raise ValidationError("Skill question requires skill.")
        if self.variant_id and self.bac_idea_id:
            if self.variant.bac_idea_id != self.bac_idea_id:
                raise ValidationError("Variant does not belong to selected BacIdea.")

    def __str__(self):
        return f"Test {self.test_id} / Q{self.order}"


class AdaptiveAnswer(TimeStampedModel):
    test_question = models.OneToOneField(
        AdaptiveTestQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="adaptive_answers",
    null=True,
    blank=True,
    )

    answer = models.JSONField(default=dict)
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    feedback = models.TextField(blank=True, default="")
    detected_misconception_codes = models.JSONField(default=list, blank=True)

    time_spent_seconds = models.PositiveIntegerField(default=0)
    hints_used = models.PositiveIntegerField(default=0)
    solution_viewed = models.BooleanField(default=False)

    class Meta:
        ordering = ["test_question__test_id", "test_question__order"]
        indexes = [
            models.Index(fields=["student", "is_correct"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self):
        if (
            self.test_question_id
            and self.student_id
            and self.test_question.test.student_id != self.student_id
        ):
            raise ValidationError("Answer student must own the test.")

    def __str__(self):
        return f"Answer {self.pk} / Q{self.test_question_id}"


# Remove photographed solution files if an answer is deleted.
from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver


@receiver(post_delete, sender=AdaptiveAnswer)
def cleanup_adaptive_answer_images(sender, instance, **kwargs):
    payload = instance.answer if isinstance(instance.answer, dict) else {}
    if payload.get("format") != "image_solution":
        return
    for item in payload.get("images") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("storage_name") or "")
        if not name.startswith("adaptive_answers/"):
            continue
        try:
            default_storage.delete(name)
        except Exception:
            # Deleting a database row must not fail because external storage is unavailable.
            pass
