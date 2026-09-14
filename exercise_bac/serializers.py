from rest_framework import serializers

from course.models import Branch, Chapter
from exercise_bac.models import ExerciseBac


class BranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ("id", "code", "name")
        read_only_fields = fields


class ChapterSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ("id", "code", "title")
        read_only_fields = fields


class ExerciseBacListSerializer(serializers.ModelSerializer):
    """
    Serializer léger utilisé par la liste paginée.

    Important: il ne lit PAS content. Ainsi le queryset peut defer("content")
    et l'ouverture de la page BAC ne transfère pas tous les JSON lourds.
    """

    chapter = ChapterSummarySerializer(read_only=True)
    branches = BranchSummarySerializer(many=True, read_only=True)
    branch_codes = serializers.SerializerMethodField()

    class Meta:
        model = ExerciseBac
        fields = (
            "id",
            "code",
            "chapter",
            "branches",
            "branch_codes",
            "year",
            "exercise_number",
            "title",
            "source_page",
            "axis_tags",
            "source_filename",
            "schema_version",
            "language",
            "direction",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_branch_codes(self, obj):
        # branches est prefetché dans la vue, donc pas de N+1 ici.
        return [branch.code for branch in obj.branches.all()]


class ExerciseBacDetailSerializer(serializers.ModelSerializer):
    """
    Serializer lourd d'UN SEUL exercice.

    Le JSON content est déplié en champs utiles au frontend afin d'éviter
    d'envoyer à la fois content ET les mêmes données une deuxième fois.
    """

    chapter = ChapterSummarySerializer(read_only=True)
    branches = BranchSummarySerializer(many=True, read_only=True)
    branch_codes = serializers.SerializerMethodField()

    statement = serializers.SerializerMethodField()
    statement_sections = serializers.SerializerMethodField()
    statement_graph_data = serializers.SerializerMethodField()
    statement_figures = serializers.SerializerMethodField()
    statement_graphs = serializers.SerializerMethodField()
    graph_data = serializers.SerializerMethodField()
    figures = serializers.SerializerMethodField()
    document_references = serializers.SerializerMethodField()

    tables = serializers.SerializerMethodField()
    statement_tables = serializers.SerializerMethodField()
    table_data = serializers.SerializerMethodField()
    data_table = serializers.SerializerMethodField()
    indicator_table = serializers.SerializerMethodField()

    questions = serializers.SerializerMethodField()
    question_groups = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    has_solutions = serializers.SerializerMethodField()

    source_pages = serializers.SerializerMethodField()
    solution_source_pages = serializers.SerializerMethodField()
    subject_number = serializers.SerializerMethodField()
    session = serializers.SerializerMethodField()
    source_reference = serializers.SerializerMethodField()
    asset_base_path = serializers.SerializerMethodField()
    source_verification = serializers.SerializerMethodField()

    class Meta:
        model = ExerciseBac
        fields = (
            "id",
            "code",
            "chapter",
            "branches",
            "branch_codes",
            "year",
            "exercise_number",
            "title",
            "source_page",
            "source_pages",
            "solution_source_pages",
            "subject_number",
            "session",
            "axis_tags",
            "statement",
            "statement_sections",
            "statement_graph_data",
            "statement_figures",
            "statement_graphs",
            "graph_data",
            "figures",
            "document_references",
            "tables",
            "statement_tables",
            "table_data",
            "data_table",
            "indicator_table",
            "questions",
            "question_groups",
            "question_count",
            "has_solutions",
            "source_reference",
            "asset_base_path",
            "source_verification",
            "source_filename",
            "schema_version",
            "language",
            "direction",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @staticmethod
    def _content(obj):
        return obj.content if isinstance(obj.content, dict) else {}

    def _get(self, obj, key, default=None):
        return self._content(obj).get(key, default)

    def get_branch_codes(self, obj):
        return [branch.code for branch in obj.branches.all()]

    def get_statement(self, obj):
        value = self._get(obj, "statement", "")
        return value if isinstance(value, str) else ""

    def get_statement_sections(self, obj):
        value = self._get(obj, "statement_sections", [])
        return value if isinstance(value, list) else []

    def get_statement_graph_data(self, obj):
        return self._get(obj, "statement_graph_data")

    @staticmethod
    def _merge_figure_lists(*collections):
        """
        Fusionne plusieurs listes de figures sans doublons.

        Les nouveaux JSON V5 utilisent surtout ``statement_figures`` alors que
        certaines anciennes versions du frontend attendent ``statement_graphs``.
        On conserve donc les deux noms dans l'API tout en évitant les doublons.
        """
        result = []
        seen = set()

        for collection in collections:
            if not isinstance(collection, list):
                continue

            for item in collection:
                if not isinstance(item, dict):
                    continue

                key = (
                    str(item.get("id") or ""),
                    str(item.get("code") or ""),
                    str(item.get("path") or item.get("src") or item.get("url") or ""),
                    str(item.get("svg") or ""),
                )

                # Si aucun identifiant n'est disponible, l'objet lui-même reste
                # unique grâce à sa représentation triée.
                if not any(key):
                    key = (repr(sorted(item.items(), key=lambda pair: pair[0])),)

                if key in seen:
                    continue

                seen.add(key)
                result.append(item)

        return result

    def get_statement_figures(self, obj):
        """
        Champ canonique des JSON physiques V5.

        Exemple:
            content["statement_figures"] = [
                {"id": "fig6", "type": "svg", "svg": "<svg ...>"}
            ]
        """
        value = self._get(obj, "statement_figures", [])
        return value if isinstance(value, list) else []

    def get_statement_graphs(self, obj):
        """
        Compatibilité descendante.

        - ancien JSON: ``statement_graphs``
        - nouveau JSON: ``statement_figures``

        Le frontend peut donc continuer à lire ``statement_graphs`` même si le
        fichier source n'utilise que ``statement_figures``.
        """
        statement_graphs = self._get(obj, "statement_graphs", [])
        statement_figures = self.get_statement_figures(obj)

        return self._merge_figure_lists(
            statement_graphs,
            statement_figures,
        )

    def get_graph_data(self, obj):
        return self._get(obj, "graph_data")

    def get_figures(self, obj):
        value = self._get(obj, "figures", [])
        return value if isinstance(value, list) else []

    def get_document_references(self, obj):
        value = self._get(obj, "document_references", [])
        return value if isinstance(value, list) else []

    def get_tables(self, obj):
        value = self._get(obj, "tables", [])
        if isinstance(value, list):
            return value
        value = self._get(obj, "statement_tables", [])
        return value if isinstance(value, list) else []

    def get_statement_tables(self, obj):
        value = self._get(obj, "statement_tables", [])
        return value if isinstance(value, list) else []

    def get_table_data(self, obj):
        return self._get(obj, "table_data")

    def get_data_table(self, obj):
        return self._get(obj, "data_table")

    def get_indicator_table(self, obj):
        return self._get(obj, "indicator_table")

    def get_questions(self, obj):
        value = self._get(obj, "questions", [])
        return value if isinstance(value, list) else []

    def get_question_groups(self, obj):
        value = self._get(obj, "question_groups", [])
        return value if isinstance(value, list) else []

    def get_question_count(self, obj):
        return len(self.get_questions(obj))

    def get_has_solutions(self, obj):
        for question in self.get_questions(obj):
            if not isinstance(question, dict):
                continue

            solution = question.get("solution")
            if not isinstance(solution, dict):
                continue

            steps = solution.get("steps", [])
            final_answer = solution.get("final_answer", "")

            if isinstance(steps, list) and steps:
                return True
            if isinstance(final_answer, str) and final_answer.strip():
                return True

        return False

    def get_source_pages(self, obj):
        value = self._get(obj, "source_pages", [])
        if isinstance(value, list):
            return value
        return [obj.source_page] if obj.source_page else []

    def get_solution_source_pages(self, obj):
        value = self._get(obj, "solution_source_pages", [])
        return value if isinstance(value, list) else []

    def get_subject_number(self, obj):
        return self._get(obj, "subject_number")

    def get_session(self, obj):
        value = self._get(obj, "session", "ordinary")
        return value if isinstance(value, str) else "ordinary"

    def get_source_reference(self, obj):
        return self._get(obj, "source_reference", "")

    def get_asset_base_path(self, obj):
        value = self._get(obj, "asset_base_path", "")
        return value if isinstance(value, str) else ""

    def get_source_verification(self, obj):
        value = self._get(obj, "source_verification", {})
        return value if isinstance(value, dict) else {}


# Compatibilité avec le reste du projet qui importe encore ExerciseBacSerializer.
ExerciseBacSerializer = ExerciseBacDetailSerializer
