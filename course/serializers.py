from rest_framework import serializers

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
        return obj.axes.filter(
            is_active=True,
        ).count()


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
class SubjectDetailSerializer(serializers.ModelSerializer):
    branches = serializers.SerializerMethodField()
    chapters = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "code",
            "name",
            "description",
            "branches",
            "chapters",
        ]

    def get_branches(self, obj):
        branches = obj.branches.all().order_by(
            "name",
        )

        return [
            {
                "id": branch.id,
                "code": branch.code,
                "name": branch.name,
            }
            for branch in branches
        ]

    def get_chapters(self, obj):
        chapters = obj.chapters.filter(
            is_active=True,
        ).order_by(
            "order",
            "title",
        )

        return ChapterSummarySerializer(
            chapters,
            many=True,
            context=self.context,
        ).data


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
    Question complète avec sa solution JSON.

    La structure de `solution` reste libre et peut changer
    selon le type de question.
    """

    solution = serializers.JSONField(
        read_only=True,
    )

    graph_data = serializers.JSONField(
        read_only=True,
    )

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

            # Graphe JSON
            "graph_data",
            "has_graph",

            # Solution JSON
            "solution",
            "has_solution",


        ]

        read_only_fields = fields

    def get_has_solution(self, obj):
        return bool(
            isinstance(obj.solution, dict)
            and len(obj.solution) > 0
        )

    def get_has_graph(self, obj):
        return bool(
            isinstance(obj.graph_data, dict)
            and len(obj.graph_data) > 0
        )

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