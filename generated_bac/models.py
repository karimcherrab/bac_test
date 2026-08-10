from django.db import models

from accounts.models import Student
from course.models import Branch, Chapter


class GeneratedBacExercise(models.Model):
    """
    تمرين جديد مولد اعتمادًا على تمارين بكالوريا حقيقية
    لها نفس الوحدة ونفس الشعبة.

    عند الإنشاء:
    - exercise يحتوي نص التمرين والأسئلة فقط.
    - solution يبقى فارغًا.

    عند طلب الحل:
    - يتم توليد solution وحفظه.
    """

    STATUS_CHOICES = [
        ("exercise_ready", "التمرين جاهز"),
        ("solution_ready", "الحل جاهز"),
        ("failed", "فشل التوليد"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="generated_bac_exercises",
        verbose_name="الطالب",
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="generated_bac_exercises",
        verbose_name="الوحدة",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="generated_bac_exercises",
        verbose_name="الشعبة",
    )

    title = models.CharField(
        max_length=255,
        verbose_name="عنوان التمرين",
    )

    exercise = models.JSONField(
        default=dict,
        verbose_name="التمرين المولد",
        help_text="يحتوي نص التمرين والأسئلة دون الحل.",
    )

    solution = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="الحل المفصل",
        help_text="يُنشأ فقط عندما يطلبه الطالب.",
    )

    reference_exercise_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="معرفات تمارين البكالوريا المرجعية",
    )

    selection_strategy = models.CharField(
        max_length=30,
        default="diverse_random",
        verbose_name="طريقة اختيار المراجع",
    )

    model_exercise = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    model_solution = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="exercise_ready",
        db_index=True,
    )

    generation_error = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "generated_bac_exercise"
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "student",
                    "chapter",
                    "branch",
                    "created_at",
                ],
                name="gen_bac_student_filter_idx",
            ),
            models.Index(
                fields=[
                    "chapter",
                    "branch",
                    "status",
                ],
                name="gen_bac_chapter_branch_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student} - "
            f"{self.chapter} - "
            f"{self.branch} - "
            f"{self.title}"
        )

    @property
    def has_solution(self):
        return bool(self.solution)


class GeneratedBacQuestionReExplanation(models.Model):
    """
    تاريخ إعادة شرح حل سؤال واحد.

    كل ضغطة على زر "لم أفهم الحل" تنشئ سجلًا جديدًا،
    لذلك يمكن للطالب الرجوع لاحقًا ومشاهدة كل الشروحات السابقة.
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="generated_bac_re_explanations",
        verbose_name="الطالب",
    )

    generated_exercise = models.ForeignKey(
        GeneratedBacExercise,
        on_delete=models.CASCADE,
        related_name="re_explanations",
        verbose_name="التمرين المولد",
    )

    question_id = models.CharField(
        max_length=80,
        db_index=True,
        verbose_name="معرف السؤال",
    )

    attempt_number = models.PositiveIntegerField(
        default=1,
        verbose_name="رقم إعادة الشرح",
    )

    explanation = models.JSONField(
        default=dict,
        verbose_name="إعادة الشرح",
    )

    model_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = "generated_bac_question_re_explanation"
        ordering = ["question_id", "attempt_number", "created_at"]
        indexes = [
            models.Index(
                fields=[
                    "student",
                    "generated_exercise",
                    "question_id",
                ],
                name="gen_bac_reexp_lookup_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "generated_exercise",
                    "question_id",
                    "attempt_number",
                ],
                name="uniq_gen_bac_reexp_attempt",
            ),
        ]

    def __str__(self):
        return (
            f"{self.generated_exercise_id} - "
            f"{self.question_id} - "
            f"attempt {self.attempt_number}"
        )
