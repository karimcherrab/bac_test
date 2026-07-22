import uuid
from django.db import models
from accounts.models import Student
from course.models import Axis

#
# class KnowledgeItem(models.Model):
#     ITEM_TYPES = [
#         ("lesson", "Lesson"),
#         ("bac_question", "BAC Question"),
#         ("method", "Method"),
#         ("concept", "Concept"),
#         ("theorem", "Theorem"),
#         ("definition", "Definition"),
#         ("formula", "Formula"),
#         ("example", "Example"),
#         ("skill", "Skill"),
#         ("roadmap", "Roadmap"),
#         ("hint", "Hint"),
#         ("mistake", "Mistake"),
#     ]
#
#     id = models.CharField(max_length=150, primary_key=True)
#
#     axis = models.ForeignKey(
#         Axis,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="items"
#     )
#
#     title = models.CharField(max_length=255)
#     item_type = models.CharField(max_length=50, choices=ITEM_TYPES)
#
#     subject = models.CharField(max_length=100, default="math")
#     branch = models.CharField(max_length=100, default="science")
#     chapter = models.CharField(max_length=100, default="sequences")
#     language = models.CharField(max_length=10, default="ar")
#
#     content = models.TextField()
#     summary = models.TextField(blank=True)
#
#     difficulty = models.CharField(max_length=50, blank=True)
#     concepts = models.JSONField(default=list, blank=True)
#     skills = models.JSONField(default=list, blank=True)
#     keywords = models.JSONField(default=list, blank=True)
#
#     source_file = models.CharField(max_length=255, blank=True)
#     source_page = models.CharField(max_length=50, blank=True)
#
#     year = models.IntegerField(null=True, blank=True)
#     exercise_title = models.CharField(max_length=100, blank=True)
#     question_number = models.CharField(max_length=50, blank=True)
#     points = models.CharField(max_length=50, blank=True)
#
#     images = models.JSONField(default=list, blank=True)
#     metadata = models.JSONField(default=dict, blank=True)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     class Meta:
#         indexes = [
#             models.Index(fields=["item_type"]),
#             models.Index(fields=["subject", "branch", "chapter"]),
#             models.Index(fields=["year"]),
#             models.Index(fields=["question_number"]),
#         ]
#
#     def __str__(self):
#         return f"{self.id} - {self.title}"


# class KnowledgeRelationship(models.Model):
#     RELATION_TYPES = [
#         ("HAS_SKILL", "Has Skill"),
#         ("USES_METHOD", "Uses Method"),
#         ("USES_FORMULA", "Uses Formula"),
#         ("SUPPORTED_BY", "Supported By"),
#         ("HAS_EXAMPLE", "Has Example"),
#         ("HAS_HINT", "Has Hint"),
#         ("COMMON_MISTAKE", "Common Mistake"),
#         ("REQUIRES", "Requires"),
#         ("RELATED_TO", "Related To"),
#         ("BELONGS_TO_CONCEPT", "Belongs To Concept"),
#     ]
#
#     source = models.ForeignKey(
#         KnowledgeItem,
#         on_delete=models.CASCADE,
#         related_name="outgoing_relationships",
#     )
#
#     target = models.ForeignKey(
#         KnowledgeItem,
#         on_delete=models.CASCADE,
#         related_name="incoming_relationships",
#     )
#
#     relation_type = models.CharField(max_length=50, choices=RELATION_TYPES)
#     metadata = models.JSONField(default=dict, blank=True)
#
#     class Meta:
#         unique_together = ("source", "target", "relation_type")
#         indexes = [
#             models.Index(fields=["relation_type"]),
#         ]
#
#     def __str__(self):
#         return f"{self.source_id} --{self.relation_type}--> {self.target_id}"
#
#
# class KnowledgeEmbedding(models.Model):
#     item = models.OneToOneField(
#         KnowledgeItem,
#         on_delete=models.CASCADE,
#         related_name="embedding",
#     )
#
#     vector = models.JSONField(default=list)
#     model_name = models.CharField(max_length=100, default="text-embedding-3-small")
#     dimension = models.IntegerField(default=1536)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return f"Embedding for {self.item_id}"


# knowledge/models.py

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from course.models import Chapter, Axis

# Modifie cet import selon l'emplacement réel de ton modèle Student.


class StudentSession(models.Model):
    """
    Session de conversation entre un étudiant et le tuteur IA.

    Une session est liée à :
    - un étudiant ;
    - un chapitre précis ;
    - éventuellement un axe actuel du chapitre.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="tutor_sessions",
        verbose_name="Étudiant",
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Titre de la session",
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_sessions",
        verbose_name="Chapitre actuel",
    )

    current_axis = models.ForeignKey(
        Axis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_sessions",
        verbose_name="Axe actuel",
    )

    current_skill = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Compétence actuelle",
    )

    current_intent = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Intention actuelle",
    )

    last_question = models.TextField(
        blank=True,
        default="",
        verbose_name="Dernière question",
    )

    last_answer = models.TextField(
        blank=True,
        default="",
        verbose_name="Dernière réponse",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Métadonnées",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Session active",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification",
    )



class StudentMessage(models.Model):
    """
    Message appartenant à une session du tuteur IA.
    """

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
        verbose_name="Session",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        db_index=True,
        verbose_name="Rôle",
    )

    content = models.TextField(
        verbose_name="Contenu",
    )

    intent = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Intention",
    )

    mode = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Mode",
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_messages",
        verbose_name="Chapitre du message",
    )

    axis = models.ForeignKey(
        Axis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_messages",
        verbose_name="Axe du message",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Métadonnées",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Date de création",
    )

