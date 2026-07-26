from rest_framework import serializers

from course.models import (
    Branch,
    Chapter,
)
from exercise_bac.models import ExerciseBac


class BranchSummarySerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Branch

        fields = (
            "id",
            "code",
            "name",
        )

        read_only_fields = fields


class ChapterSummarySerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Chapter

        fields = (
            "id",
            "code",
            "title",
        )

        read_only_fields = fields


class ExerciseBacSerializer(
    serializers.ModelSerializer
):
    chapter = ChapterSummarySerializer(
        read_only=True,
    )

    branches = BranchSummarySerializer(
        many=True,
        read_only=True,
    )

    branch_codes = serializers.SerializerMethodField()

    statement = serializers.SerializerMethodField()

    statement_graph_data = (
        serializers.SerializerMethodField()
    )

    has_statement_graph = (
        serializers.SerializerMethodField()
    )

    questions = serializers.SerializerMethodField()

    question_count = serializers.SerializerMethodField()

    has_solutions = serializers.SerializerMethodField()

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
            "statement",
            "statement_graph_data",
            "has_statement_graph",
            "questions",
            "question_count",
            "has_solutions",
            "content",
            "source_filename",
            "schema_version",
            "language",
            "direction",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields

    def get_branch_codes(
        self,
        obj,
    ):
        return [
            branch.code
            for branch in obj.branches.all()
        ]

    def get_statement(
        self,
        obj,
    ):
        if not isinstance(
            obj.content,
            dict,
        ):
            return ""

        return obj.content.get(
            "statement",
            "",
        )

    def get_statement_graph_data(
        self,
        obj,
    ):
        if not isinstance(
            obj.content,
            dict,
        ):
            return None

        return obj.content.get(
            "statement_graph_data",
        )

    def get_has_statement_graph(
        self,
        obj,
    ):
        graph_data = (
            self.get_statement_graph_data(obj)
        )

        return bool(graph_data)

    def get_questions(
        self,
        obj,
    ):
        if not isinstance(
            obj.content,
            dict,
        ):
            return []

        questions = obj.content.get(
            "questions",
            [],
        )

        if not isinstance(
            questions,
            list,
        ):
            return []

        return questions

    def get_question_count(
        self,
        obj,
    ):
        return len(
            self.get_questions(obj)
        )

    def get_has_solutions(
        self,
        obj,
    ):
        questions = self.get_questions(obj)

        if not questions:
            return False

        for question in questions:
            if not isinstance(
                question,
                dict,
            ):
                continue

            solution = question.get(
                "solution",
            )

            if not isinstance(
                solution,
                dict,
            ):
                continue

            steps = solution.get(
                "steps",
                [],
            )

            final_answer = solution.get(
                "final_answer",
                "",
            )

            has_steps = (
                isinstance(steps, list)
                and len(steps) > 0
            )

            has_final_answer = (
                isinstance(final_answer, str)
                and bool(final_answer.strip())
            )

            if has_steps or has_final_answer:
                return True

        return False