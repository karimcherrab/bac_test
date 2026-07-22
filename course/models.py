from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import Student, Branch
from django.db import models



class Subject(models.Model):
    code = models.CharField(
        max_length=100,
        unique=True,
    )

    name = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        blank=True,
    )



    theme = models.CharField(
        max_length=30,
        default="purple",
    )



    icon = models.CharField(
        max_length=50,
        default="Calculator",
    )

    branches = models.ManyToManyField(
        Branch,
        related_name="subjects",
        blank=True,
    )

    def __str__(self):
        return self.name


    class Meta:
        ordering = ["name"]

class Chapter(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="chapters",
    )

    code = models.CharField(
        max_length=100,
    )

    title = models.CharField(
        max_length=255,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    def __str__(self):
        return f"{self.subject.name} - {self.title}"

    class Meta:
        ordering = ["subject", "order"]

        constraints = [
            models.UniqueConstraint(
                fields=["subject", "code"],
                name="unique_chapter_code_per_subject",
            )
        ]


class Axis(models.Model):
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="axes",
    )

    tag = models.CharField(
        max_length=100,
    )

    title = models.CharField(
        max_length=255,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    # PostgreSQL stockera ce champ sous forme JSONB.
    content = models.JSONField(
        default=dict,
        blank=True,
    )

    def __str__(self):
        return f"{self.tag} - {self.title}"

    class Meta:
        ordering = ["chapter", "order"]

        constraints = [
            models.UniqueConstraint(
                fields=["chapter", "tag"],
                name="unique_axis_tag_per_chapter",
            )
        ]




from django.core.exceptions import ValidationError
from django.db import models


class Question(models.Model):

    DIFFICULTY_CHOICES = [
        ("easy", "سهل"),
        ("medium", "متوسط"),
        ("hard", "صعب"),
    ]

    QUESTION_TYPE_CHOICES = [
        ("bac", "تمرين بكالوريا"),
        ("guided", "تمرين موجه"),
        ("practice", "تمرين تطبيقي"),
        ("quiz", "اختبار قصير"),
    ]

    axis = models.ForeignKey(
        "Axis",
        on_delete=models.CASCADE,
        related_name="questions",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="questions",
        null=True,
        blank=True,
    )

    # Correspond au champ "id" du fichier JSON.
    code = models.CharField(
        max_length=180,
    )

    # Numéro de la question.
    # Exemples : 1, 2-a, 2-b, II-3.
    number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    # Exemple : exercise_1, exercise_3, exercise_2_II.
    exercise = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # Texte original ou texte principal de la question.
    text = models.TextField()

    # Texte complet permettant d'afficher la question seule.
    standalone_text = models.TextField(
        blank=True,
        default="",
    )

    # Données nécessaires à la compréhension de la question.
    context = models.TextField(
        blank=True,
        default="",
    )

    standalone_support = models.JSONField(
        default=list,
        blank=True,
    )

    # Texte original avant adaptation.
    original_text = models.TextField(
        blank=True,
        default="",
    )

    question_type = models.CharField(
        max_length=30,
        choices=QUESTION_TYPE_CHOICES,
        default="bac",
    )

    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
    )

    skill = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    year = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    source_file = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    source_page = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    secondary_tags = models.JSONField(
        default=list,
        blank=True,
    )

    depends_on = models.JSONField(
        default=list,
        blank=True,
    )

    images = models.JSONField(
        default=list,
        blank=True,
    )

    # Solution complète.
    solution = models.JSONField(
        default=dict,
        blank=True,
    )

    # Données du graphe destinées au frontend React.
    #
    # Exemple :
    # {
    #     "graph_type": "cobweb",
    #     "function": {...},
    #     "identity": {...},
    #     "sequence_values": [...],
    #     "cobweb_points": [...],
    #     "viewport": {...},
    #     "react_data": {...}
    # }
    graph_data = models.JSONField(
        default=dict,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    is_standalone = models.BooleanField(
        default=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "order",
            "year",
            "exercise",
            "number",
        ]

    def __str__(self):
        return (
            f"{self.code} - "
            f"{self.title or self.text[:50]}"
        )
from django.conf import settings
from django.db import models


class ReExplainStepHistory(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="re_explain_step_history",
    )

    axis = models.ForeignKey(
        Axis,
        on_delete=models.CASCADE,
        related_name="re_explain_step_history",
    )

    step_id = models.CharField(
        max_length=150,
        db_index=True,
    )

    step_title = models.CharField(
        max_length=255,
    )

    step_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    # نسخة كاملة من المرحلة وقت طلب الشرح.
    step_data = models.JSONField(
        default=dict,
    )

    student_question = models.TextField()

    # جواب الذكاء الاصطناعي.
    answer = models.JSONField(
        default=dict,
    )

    model_name = models.CharField(
        max_length=150,
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
        db_table = "re_explain_step_history"

        ordering = [
            "-updated_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "student",
                    "step_id",
                ],
                name="student_step_rexp_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.step_id} - "
            f"{self.step_title}"
        )




from django.db import models


# class BacExercise(models.Model):
#     class Difficulty(models.TextChoices):
#         EASY = "easy", "سهل"
#         MEDIUM = "medium", "متوسط"
#         HARD = "hard", "صعب"
#         MEDIUM_HARD = "medium_hard", "متوسط إلى صعب"
#
#     exercise_id = models.CharField(
#         max_length=150,
#         unique=True,
#         db_index=True,
#         verbose_name="المعرف الخارجي",
#     )
#
#     chapter = models.ForeignKey(
#         Chapter,
#         on_delete=models.CASCADE,
#         related_name="bac_exercises",
#         verbose_name="الفصل",
#     )
#
#     axes = models.ManyToManyField(
#         Axis,
#         related_name="bac_exercises",
#         blank=True,
#         verbose_name="المحاور المرتبطة",
#     )
#
#     year = models.PositiveIntegerField(
#         db_index=True,
#         verbose_name="السنة",
#     )
#
#     branch = models.CharField(
#         max_length=150,
#         default="علوم تجريبية",
#         verbose_name="الشعبة",
#     )
#
#     session = models.CharField(
#         max_length=150,
#         blank=True,
#         default="",
#         verbose_name="الدورة",
#     )
#
#     exercise_number = models.CharField(
#         max_length=150,
#         blank=True,
#         default="",
#         verbose_name="رقم التمرين",
#     )
#
#     points = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         null=True,
#         blank=True,
#         verbose_name="النقاط",
#     )
#
#     pdf_page = models.PositiveIntegerField(
#         null=True,
#         blank=True,
#         verbose_name="صفحة المصدر",
#     )
#
#     title = models.CharField(
#         max_length=255,
#         verbose_name="عنوان التمرين",
#     )
#
#     difficulty = models.CharField(
#         max_length=30,
#         choices=Difficulty.choices,
#         default=Difficulty.MEDIUM,
#         db_index=True,
#         verbose_name="الصعوبة",
#     )
#
#     statement = models.JSONField(
#         default=dict,
#         verbose_name="نص التمرين",
#     )
#
#     solution = models.JSONField(
#         default=dict,
#         verbose_name="الحل",
#     )
#
#     graph = models.JSONField(
#         null=True,
#         blank=True,
#         verbose_name="بيانات الرسم",
#     )
#
#     images = models.JSONField(
#         default=list,
#         blank=True,
#         verbose_name="الصور",
#     )
#
#     source = models.JSONField(
#         default=dict,
#         blank=True,
#         verbose_name="بيانات المصدر",
#     )
#
#     raw_data = models.JSONField(
#         default=dict,
#         blank=True,
#         verbose_name="JSON الأصلي",
#     )
#
#     schema_version = models.CharField(
#         max_length=30,
#         default="1.0",
#     )
#
#     language = models.CharField(
#         max_length=10,
#         default="ar",
#     )
#
#     direction = models.CharField(
#         max_length=10,
#         default="rtl",
#     )
#
#     math_format = models.CharField(
#         max_length=30,
#         default="LaTeX",
#     )
#
#     is_active = models.BooleanField(
#         default=True,
#         db_index=True,
#     )
#
#     order = models.PositiveIntegerField(
#         default=0,
#     )
#
#     created_at = models.DateTimeField(
#         auto_now_add=True,
#     )
#
#     updated_at = models.DateTimeField(
#         auto_now=True,
#     )
#
#     class Meta:
#         ordering = [
#             "-year",
#             "order",
#             "id",
#         ]
#
#         indexes = [
#             models.Index(
#                 fields=["year", "branch"],
#             ),
#             models.Index(
#                 fields=["is_active", "year"],
#             ),
#         ]
#
#         verbose_name = "تمرين بكالوريا"
#         verbose_name_plural = "تمارين البكالوريا"
#
#     def __str__(self):
#         return (
#             f"{self.year} - "
#             f"{self.exercise_number} - "
#             f"{self.title}"
#         )