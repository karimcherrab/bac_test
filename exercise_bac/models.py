from django.db import models

from accounts.models import Student
from course.models import Branch, Chapter


class ExerciseBac(models.Model):
    code = models.CharField(
        max_length=150,

        db_index=True,
        verbose_name="Code unique",
    )

    branches = models.ManyToManyField(
        Branch,
        related_name="bac_exercises",
        blank=True,
        verbose_name="Filières",
        help_text=(
            "Filières concernées par cet exercice. "
            "Un même exercice peut appartenir à plusieurs filières."
        ),
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="chapter_exercises_bac",
        null=True,
        blank=True,
        verbose_name="Chapitre",
    )

    year = models.PositiveSmallIntegerField(
        db_index=True,
        verbose_name="Année du baccalauréat",
    )

    exercise_number = models.PositiveSmallIntegerField(
        verbose_name="Numéro de l'exercice",
    )

    title = models.CharField(
        max_length=255,
        verbose_name="Titre",
    )

    source_page = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Page source",
    )

    axis_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tags des axes",
        help_text=(
            "Liste des axes pédagogiques liés à l'exercice."
        ),
    )

    content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Contenu complet",
        help_text=(
            "Contient le texte, les questions, "
            "les solutions, les tableaux et les graphiques."
        ),
    )

    source_filename = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Fichier JSON source",
    )

    schema_version = models.CharField(
        max_length=30,
        default="1.0",
        blank=True,
        verbose_name="Version du schéma JSON",
    )

    language = models.CharField(
        max_length=10,
        default="ar",
        verbose_name="Langue",
    )

    direction = models.CharField(
        max_length=10,
        default="rtl",
        verbose_name="Direction du texte",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Actif",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "exercise_bac"

        verbose_name = "Exercice du baccalauréat"
        verbose_name_plural = "Exercices du baccalauréat"

        ordering = [
            "-year",
            "exercise_number",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "chapter",
                    "is_active",
                    "year",
                ],
                name="bac_chapter_active_year_idx",
            ),
            models.Index(
                fields=[
                    "year",
                    "exercise_number",
                ],
                name="bac_year_number_idx",
            ),
            models.Index(
                fields=[
                    "is_active",
                    "year",
                ],
                name="bac_active_year_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Bac {self.year} - "
            f"Exercice {self.exercise_number} - "
            f"{self.title}"
        )

    @property
    def branch_codes(self):
        return list(
            self.branches.values_list(
                "code",
                flat=True,
            )
        )

    @property
    def branch_names(self):
        return list(
            self.branches.values_list(
                "name",
                flat=True,
            )
        )

    @property
    def statement(self):
        if not isinstance(self.content, dict):
            return ""

        value = self.content.get(
            "statement",
            "",
        )

        return value if isinstance(value, str) else ""

    @property
    def statement_sections(self):
        if not isinstance(self.content, dict):
            return []

        value = self.content.get(
            "statement_sections",
            [],
        )

        return value if isinstance(value, list) else []

    @property
    def statement_graph_data(self):
        if not isinstance(self.content, dict):
            return None

        return self.content.get(
            "statement_graph_data",
        )

    @property
    def has_statement_graph(self):
        return bool(
            self.statement_graph_data
        )

    @property
    def questions(self):
        if not isinstance(self.content, dict):
            return []

        questions = self.content.get(
            "questions",
            [],
        )

        return questions if isinstance(
            questions,
            list,
        ) else []

    @property
    def question_count(self):
        return len(self.questions)


class BacStepReExplanation(models.Model):
    """
    Réexplication simplifiée d'une étape
    pour un étudiant donné.
    """

    REQUEST_TYPE_CHOICES = [
        (
            "very_simple",
            "شرح مبسط جدًا",
        ),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="bac_step_reexplanations",
        verbose_name="Étudiant",
    )

    exercise = models.ForeignKey(
        ExerciseBac,
        on_delete=models.CASCADE,
        related_name="step_reexplanations",
        verbose_name="Exercice du baccalauréat",
    )

    question_id = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name="Identifiant de la question",
    )

    step_number = models.PositiveIntegerField(
        db_index=True,
        verbose_name="Numéro de l'étape",
    )

    step_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Titre de l'étape",
    )

    request_type = models.CharField(
        max_length=30,
        choices=REQUEST_TYPE_CHOICES,
        default="very_simple",
        verbose_name="Type de demande",
    )

    explanation = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Réexplication générée",
    )

    model = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Modèle IA",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "bac_step_reexplanation"

        verbose_name = "Réexplication d'une étape"
        verbose_name_plural = "Réexplications des étapes"

        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "student",
                    "exercise",
                    "question_id",
                    "step_number",
                ],
                name="bac_reexp_student_step_idx",
            ),
            models.Index(
                fields=[
                    "exercise",
                    "question_id",
                    "step_number",
                ],
                name="bac_reexp_exercise_step_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student} - "
            f"{self.exercise.code} - "
            f"Question {self.question_id} - "
            f"Étape {self.step_number}"
        )