from rest_framework import serializers

from exercise_bac.models import ExerciseBac
from .models import (
    Axis,
    Branch,
    Chapter,
    Question,
    Subject,
)


class AxisSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Axis
        fields = [
            "id",
            "tag",
            "title",
            "order",
            "is_active",
        ]


class AxisDetailSerializer(serializers.ModelSerializer):
    chapter_id = serializers.IntegerField(
        source="chapter.id",
        read_only=True,
    )

    chapter_code = serializers.CharField(
        source="chapter.code",
        read_only=True,
    )

    chapter_title = serializers.CharField(
        source="chapter.title",
        read_only=True,
    )

    subject_id = serializers.IntegerField(
        source="chapter.subject.id",
        read_only=True,
    )

    subject_code = serializers.CharField(
        source="chapter.subject.code",
        read_only=True,
    )

    subject_name = serializers.CharField(
        source="chapter.subject.name",
        read_only=True,
    )

    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = Axis
        fields = [
            "id",
            "tag",
            "title",
            "order",
            "is_active",
            "content",
            "chapter_id",
            "chapter_code",
            "chapter_title",
            "subject_id",
            "subject_code",
            "subject_name",
            "questions_count",
        ]

    def get_questions_count(self, obj):
        return obj.questions.filter(
            is_active=True,
        ).count()


from rest_framework import serializers

from course.models import Chapter


class ChapterSummarySerializer(serializers.ModelSerializer):
    axes_count = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = [
            "id",
            "code",
            "title",
            "order",
            "is_active",
            "axes_count",
        ]

    def get_axes_count(self, obj):
        branch_code = self.context.get("branch_code")

        axes = obj.axes.filter(
            is_active=True,
        )

        if branch_code:
            axes = axes.filter(
                branches__code=branch_code,
            )

        return axes.distinct().count()

class ChapterDetailSerializer(serializers.ModelSerializer):
    subject_id = serializers.IntegerField(
        source="subject.id",
        read_only=True,
    )

    subject_code = serializers.CharField(
        source="subject.code",
        read_only=True,
    )

    subject_name = serializers.CharField(
        source="subject.name",
        read_only=True,
    )

    axes = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = [
            "id",
            "code",
            "title",
            "order",
            "is_active",
            "subject_id",
            "subject_code",
            "subject_name",
            "axes",
        ]

    def get_axes(self, obj):
        axes = obj.axes.filter(
            is_active=True,
        ).order_by(
            "order",
            "title",
        )

        return AxisSummarySerializer(
            axes,
            many=True,
            context=self.context,
        ).data


class SubjectSummarySerializer(serializers.ModelSerializer):
    branches = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="code",
    )

    class Meta:
        model = Subject
        fields = [
            "id",
            "code",
            "name",
            "description",
            "theme",
            "icon",
            "branches",
        ]

class SubjectCreateSerializer(serializers.ModelSerializer):
    branch_codes = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
    )

    class Meta:
        model = Subject
        fields = [
            "code",
            "name",
            "description",
            "theme",
            "icon",
            "branch_codes",
        ]

    def create(self, validated_data):
        branch_codes = validated_data.pop(
            "branch_codes",
            [],
        )

        subject = Subject.objects.create(
            **validated_data,
        )

        branches = Branch.objects.filter(
            code__in=branch_codes,
        )

        subject.branches.set(branches)

        return subject
from django.db.models import Q

from rest_framework import serializers

from course.models import (
    Subject,
    Axis,
    Question,
)



from rest_framework import serializers

from course.models import (
    Subject,
    Axis,
    Question,
)

# عدّل اسم التطبيق إذا كان مختلفًا عندك


class SubjectDetailSerializer(
    serializers.ModelSerializer,
):
    user_branch = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()

    class Meta:
        model = Subject

        fields = [
            "id",
            "code",
            "name",
            "description",
            "user_branch",
            "statistics",
        ]

    # =========================================================
    # Student
    # =========================================================

    def get_student(self):
        request = self.context.get(
            "request",
        )

        if not request:
            return None

        student = getattr(
            request,
            "user",
            None,
        )

        if not student:
            return None

        if not getattr(
            student,
            "is_authenticated",
            False,
        ):
            return None

        return student

    # =========================================================
    # Student branch
    # =========================================================

    def get_student_branch(self):
        student = self.get_student()

        if not student:
            return None

        return getattr(
            student,
            "branch",
            None,
        )

    # =========================================================
    # User branch
    # =========================================================

    def get_user_branch(
        self,
        obj,
    ):
        branch = self.get_student_branch()

        if not branch:
            return None

        return {
            "id": branch.id,
            "code": branch.code,
            "name": branch.name,
        }

    # =========================================================
    # Statistics
    # =========================================================

    def get_statistics(
        self,
        obj,
    ):
        # =====================================================
        # 1. Chapters count
        # =====================================================

        chapters_count = (
            obj.chapters
            .filter(
                is_active=True,
            )
            .count()
        )

        # =====================================================
        # 2. Axes / lessons count
        # =====================================================
        #
        # نحسب جميع المحاور التابعة لهذه المادة.
        #

        axes_count = (
            Axis.objects
            .filter(
                chapter__subject=obj,
                chapter__is_active=True,
                is_active=True,
            )
            .distinct()
            .count()
        )

        # =====================================================
        # 3. Exercises / Questions count
        # =====================================================
        #
        # جميع الأسئلة الموجودة داخل محاور هذه المادة.
        #

        exercises_count = (
            Question.objects
            .filter(
                axis__chapter__subject=obj,
                axis__chapter__is_active=True,
                axis__is_active=True,
                is_active=True,
            )
            .distinct()
            .count()
        )

        # =====================================================
        # 4. Complete BAC Exercises count
        # =====================================================
        #
        # المهم:
        # لا نقوم بفلترة branches هنا.
        #
        # كل ExerciseBac مرتبط بـ Chapter.
        # وكل Chapter مرتبط بـ Subject.
        #
        # لذلك نحسب جميع تمارين البكالوريا
        # التابعة لفصول هذه المادة.
        #

        bac_exercises_count = (
            ExerciseBac.objects
            .filter(
                chapter__subject=obj,
                is_active=True,
            )
            .count()
        )

        # =====================================================
        # Response
        # =====================================================

        return {
            "chapters_count":
                chapters_count,

            "axes_count":
                axes_count,

            "exercises_count":
                exercises_count,

            "bac_exercises_count":
                bac_exercises_count,
        }

class BranchSerializer(serializers.ModelSerializer):
    subjects_count = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "code",
            "name",
            "subjects_count",
        ]

    def get_subjects_count(self, obj):
        return obj.subjects.count()


class BranchDetailSerializer(serializers.ModelSerializer):
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "code",
            "name",
            "subjects",
        ]

    def get_subjects(self, obj):
        subjects = obj.subjects.all().order_by(
            "name",
        )

        return SubjectSummarySerializer(
            subjects,
            many=True,
            context=self.context,
        ).data


class QuestionSummarySerializer(serializers.ModelSerializer):
    """
    Version légère d'une question.

    Elle retourne les informations principales sans imposer
    une structure fixe à la solution JSON.
    """

    has_solution = serializers.SerializerMethodField()
    has_graph = serializers.SerializerMethodField()
    displayed_text = serializers.CharField(
        read_only=True,
    )

    axis_id = serializers.IntegerField(
        source="axis.id",
        read_only=True,
    )

    axis_tag = serializers.CharField(
        source="axis.tag",
        read_only=True,
    )

    axis_title = serializers.CharField(
        source="axis.title",
        read_only=True,
    )

    branch_id = serializers.IntegerField(
        source="branch.id",
        read_only=True,
        allow_null=True,
    )

    branch_code = serializers.CharField(
        source="branch.code",
        read_only=True,
        allow_null=True,
    )

    branch_name = serializers.CharField(
        source="branch.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Question

        fields = [
            "id",
            "code",
            "number",
            "exercise",
            "title",

            # Textes
            "text",
            "standalone_text",
            "displayed_text",
            "context",
            "standalone_support",
            "original_text",

            # Classification
            "question_type",
            "difficulty",
            "skill",
            "year",

            # Source
            "source_file",
            "source_page",

            # Relations et métadonnées
            "secondary_tags",
            "depends_on",
            "images",
            "is_standalone",
            "is_active",
            "order",

            # Axe
            "axis_id",
            "axis_tag",
            "axis_title",

            # Branche
            "branch_id",
            "branch_code",
            "branch_name",

            # Graphe et solution
            "graph_data",
            "has_graph",
            "has_solution",
        ]

    def get_has_solution(self, obj):
        """
        Retourne True uniquement si solution contient
        un objet JSON non vide.
        """

        return bool(
            isinstance(obj.solution, dict)
            and len(obj.solution) > 0
        )

    def get_has_graph(self, obj):
        """
        Retourne True si graph_data contient
        un objet JSON non vide.
        """

        return bool(
            isinstance(obj.graph_data, dict)
            and len(obj.graph_data) > 0
        )


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Question complète avec :
    - solution JSON
    - graph_data JSON
    - documents JSON

    Documents fonctionne dans les deux cas :
    1. Question.documents existe dans le Model
    2. documents est sauvegardé dans metadata["documents"]
    """

    solution = serializers.JSONField(
        read_only=True,
    )

    graph_data = serializers.JSONField(
        read_only=True,
    )

    # =========================================================
    # DOCUMENTS
    # =========================================================

    documents = serializers.SerializerMethodField()

    has_documents = serializers.SerializerMethodField()

    document_count = serializers.SerializerMethodField()

    # =========================================================
    # STATES
    # =========================================================

    has_solution = serializers.SerializerMethodField()

    has_graph = serializers.SerializerMethodField()

    displayed_text = serializers.CharField(
        read_only=True,
    )

    # =========================================================
    # AXIS
    # =========================================================

    axis_id = serializers.IntegerField(
        source="axis.id",
        read_only=True,
    )

    axis_tag = serializers.CharField(
        source="axis.tag",
        read_only=True,
    )

    axis_title = serializers.CharField(
        source="axis.title",
        read_only=True,
    )

    # =========================================================
    # CHAPTER
    # =========================================================

    chapter_id = serializers.IntegerField(
        source="axis.chapter.id",
        read_only=True,
    )

    chapter_code = serializers.CharField(
        source="axis.chapter.code",
        read_only=True,
    )

    chapter_title = serializers.CharField(
        source="axis.chapter.title",
        read_only=True,
    )

    # =========================================================
    # SUBJECT
    # =========================================================

    subject_id = serializers.IntegerField(
        source="axis.chapter.subject.id",
        read_only=True,
    )

    subject_code = serializers.CharField(
        source="axis.chapter.subject.code",
        read_only=True,
    )

    subject_name = serializers.CharField(
        source="axis.chapter.subject.name",
        read_only=True,
    )

    # =========================================================
    # BRANCH
    # =========================================================

    branch = serializers.SerializerMethodField()

    class Meta:
        model = Question

        fields = [
            "id",
            "code",
            "number",
            "exercise",
            "title",

            # Textes
            "text",
            "standalone_text",
            "displayed_text",
            "context",
            "standalone_support",
            "original_text",

            # Classification
            "question_type",
            "difficulty",
            "skill",
            "year",

            # Source
            "source_file",
            "source_page",

            # Informations JSON
            "secondary_tags",
            "depends_on",
            "images",
            "metadata",

            # Documents
            "documents",
            "has_documents",
            "document_count",

            # États
            "is_standalone",
            "is_active",
            "order",

            # Axe
            "axis_id",
            "axis_tag",
            "axis_title",

            # Chapitre
            "chapter_id",
            "chapter_code",
            "chapter_title",

            # Matière
            "subject_id",
            "subject_code",
            "subject_name",

            # Branche
            "branch",

            # Graphe
            "graph_data",
            "has_graph",

            # Solution
            "solution",
            "has_solution",
        ]

        read_only_fields = fields

    # =========================================================
    # DOCUMENTS
    # =========================================================

    def _get_documents(self, obj):
        """
        Récupère les documents depuis :

        1. obj.documents si le Model possède ce champ
        2. metadata["documents"] sinon
        """

        # -----------------------------------------------------
        # 1. Champ direct dans Question
        # -----------------------------------------------------

        if hasattr(obj, "documents"):
            documents = getattr(
                obj,
                "documents",
                None,
            )

            if isinstance(documents, list):
                return documents

        # -----------------------------------------------------
        # 2. Fallback metadata
        # -----------------------------------------------------

        metadata = getattr(
            obj,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            documents = metadata.get(
                "documents",
                [],
            )

            if isinstance(documents, list):
                return documents

        return []

    def get_documents(self, obj):
        return self._get_documents(obj)

    def get_has_documents(self, obj):
        return len(
            self._get_documents(obj)
        ) > 0

    def get_document_count(self, obj):
        return len(
            self._get_documents(obj)
        )

    # =========================================================
    # SOLUTION
    # =========================================================

    def get_has_solution(self, obj):
        return bool(
            isinstance(obj.solution, dict)
            and len(obj.solution) > 0
        )

    # =========================================================
    # GRAPH
    # =========================================================

    def get_has_graph(self, obj):
        return bool(
            isinstance(obj.graph_data, dict)
            and len(obj.graph_data) > 0
        )

    # =========================================================
    # BRANCH
    # =========================================================

    def get_branch(self, obj):
        if obj.branch is None:
            return None

        return {
            "id": obj.branch.id,
            "code": obj.branch.code,
            "name": obj.branch.name,
        }


class QuestionWriteSerializer(serializers.ModelSerializer):
    """
    Serializer pour créer ou modifier une question.

    La solution est directement envoyée comme objet JSON.
    """

    solution = serializers.JSONField(
        required=False,
    )

    graph_data = serializers.JSONField(
        required=False,
    )

    class Meta:
        model = Question

        fields = [
            "axis",
            "branch",
            "code",
            "number",
            "exercise",
            "title",

            # Textes
            "text",
            "standalone_text",
            "context",
            "standalone_support",
            "original_text",

            # Classification
            "question_type",
            "difficulty",
            "skill",
            "year",

            # Source
            "source_file",
            "source_page",

            # JSON
            "secondary_tags",
            "depends_on",
            "images",
            "solution",
            "graph_data",
            "metadata",

            # États
            "is_standalone",
            "is_active",
            "order",
        ]

    def validate_solution(self, value):
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Le champ solution doit contenir un objet JSON."
            )

        return value

    def validate_graph_data(self, value):
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Le champ graph_data doit contenir un objet JSON."
            )

        return value

    def validate_secondary_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "secondary_tags doit contenir une liste JSON."
            )

        return value

    def validate_depends_on(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "depends_on doit contenir une liste JSON."
            )

        return value

    def validate_images(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "images doit contenir une liste JSON."
            )

        return value

    def validate_standalone_support(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "standalone_support doit contenir une liste JSON."
            )

        return value

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "metadata doit contenir un objet JSON."
            )

        return value

    def validate(self, attrs):
        """
        Vérifie qu'une question autonome contient suffisamment
        d'informations pour être comprise seule.
        """

        instance = getattr(
            self,
            "instance",
            None,
        )

        is_standalone = attrs.get(
            "is_standalone",
            getattr(
                instance,
                "is_standalone",
                True,
            ),
        )

        text = attrs.get(
            "text",
            getattr(
                instance,
                "text",
                "",
            ),
        )

        standalone_text = attrs.get(
            "standalone_text",
            getattr(
                instance,
                "standalone_text",
                "",
            ),
        )

        context = attrs.get(
            "context",
            getattr(
                instance,
                "context",
                "",
            ),
        )

        standalone_support = attrs.get(
            "standalone_support",
            getattr(
                instance,
                "standalone_support",
                [],
            ),
        )

        if is_standalone:
            has_complete_content = any(
                [
                    bool(
                        str(
                            standalone_text or ""
                        ).strip()
                    ),
                    bool(
                        str(
                            text or ""
                        ).strip()
                        and str(
                            context or ""
                        ).strip()
                    ),
                    bool(
                        str(
                            text or ""
                        ).strip()
                        and standalone_support
                    ),
                ]
            )

            if not has_complete_content:
                raise serializers.ValidationError(
                    {
                        "standalone_text": (
                            "Une question autonome doit contenir "
                            "standalone_text, ou text avec context, "
                            "ou text avec standalone_support."
                        )
                    }
                )

        return attrs


class AxisQuestionsSerializer(serializers.ModelSerializer):
    """
    Retourne un axe avec toutes ses questions actives.
    """

    questions = serializers.SerializerMethodField()

    class Meta:
        model = Axis

        fields = [
            "id",
            "tag",
            "title",
            "order",
            "is_active",
            "questions",
        ]

    def get_questions(self, obj):
        questions = (
            obj.questions
            .filter(
                is_active=True,
            )
            .select_related(
                "axis",
                "axis__chapter",
                "axis__chapter__subject",
                "branch",
            )
            .order_by(
                "year",
                "order",
                "number",
                "id",
            )
        )

        return QuestionDetailSerializer(
            questions,
            many=True,
            context=self.context,
        ).data


# ============================================================
# AI - حل التمرين بطريقة شديدة التبسيط
# ============================================================

class QuestionSimpleSolutionRequestSerializer(serializers.Serializer):
    # الحقل اختياري؛ question_id يأتي من URL.
    regenerate = serializers.BooleanField(required=False, default=False)


class SimpleGivenItemSerializer(serializers.Serializer):
    label = serializers.CharField(allow_blank=True)
    value = serializers.CharField(allow_blank=True)
    meaning = serializers.CharField(allow_blank=True)


class SimpleSolutionStepSerializer(serializers.Serializer):
    order = serializers.IntegerField(min_value=1)
    title = serializers.CharField()
    explanation = serializers.CharField(allow_blank=True)
    formula = serializers.CharField(allow_blank=True)
    calculation = serializers.CharField(allow_blank=True)
    result = serializers.CharField(allow_blank=True)


class SimpleSolutionPayloadSerializer(serializers.Serializer):
    teacher_intro = serializers.CharField()
    what_is_given = SimpleGivenItemSerializer(many=True)
    what_is_required = serializers.CharField(allow_blank=True)
    idea = serializers.CharField(allow_blank=True)
    steps = SimpleSolutionStepSerializer(many=True)
    final_answer = serializers.CharField()
    verification = serializers.CharField(allow_blank=True)
    memory_tip = serializers.CharField(allow_blank=True)


class QuestionSimpleSolutionResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    exists = serializers.BooleanField()
    saved = serializers.BooleanField()
    source = serializers.ChoiceField(choices=["saved", "generated", "none"])
    question_id = serializers.IntegerField()
    subject = serializers.CharField(allow_blank=True)
    model = serializers.CharField(allow_blank=True)
    simple_solution = SimpleSolutionPayloadSerializer(
        required=False,
        allow_null=True,
    )
    created_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    updated_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
