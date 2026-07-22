from typing import Any

from rest_framework import serializers

from exercise_generation.models import (
    GeneratedExercise,
    GeneratedExerciseAlternativeSolution,
)




class ExerciseGenerationRequestSerializer(serializers.Serializer):
    axis_id = serializers.IntegerField(min_value=1)
    count = serializers.IntegerField(min_value=1, max_value=5, default=1)
    save_to_database = serializers.BooleanField(default=True)


class AlternativeSolutionRequestSerializer(serializers.Serializer):
    simplification_level = serializers.ChoiceField(
        choices=["simple", "very_simple"],
        default="very_simple",
        required=False,
    )


class GeneratedExerciseAlternativeSolutionSerializer(serializers.ModelSerializer):
    exercise_id = serializers.IntegerField(source="exercise.id", read_only=True)

    class Meta:
        model = GeneratedExerciseAlternativeSolution
        fields = [
            "id",
            "exercise_id",
            "explanation",
            "solution_steps",
            "final_answer",
            "model_name",
            "created_at",
        ]
        read_only_fields = fields


class GeneratedExerciseSerializer(serializers.ModelSerializer):
    axis_id = serializers.IntegerField(source="axis.id", read_only=True)
    axis_title = serializers.CharField(source="axis.title", read_only=True)
    axis_tag = serializers.CharField(source="axis.tag", read_only=True)
    alternative_solutions = GeneratedExerciseAlternativeSolutionSerializer(
        many=True,
        read_only=True,
    )

    solution_strategy = serializers.SerializerMethodField()
    solution_explanation = serializers.SerializerMethodField()
    common_mistakes = serializers.SerializerMethodField()
    alternative_method = serializers.SerializerMethodField()
    reference_question_ids = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedExercise
        fields = [
            "id",
            "axis_id",
            "axis_title",
            "axis_tag",
            "title",
            "question",
            "difficulty",
            "exercise_type",
            "skill",
            "hints",
            "solution_strategy",
            "solution_explanation",
            "solution_steps",
            "final_answer",
            "verification",
            "common_mistake",
            "common_mistakes",
            "alternative_method",
            "requires_graph",
            "graph_data",
            "reference_question_ids",
            "model_name",
            "raw_ai_response",
            "is_active",
            "created_at",
            "updated_at",
            "alternative_solutions",
        ]
        read_only_fields = fields

    @staticmethod
    def _normalized(obj: GeneratedExercise) -> dict[str, Any]:
        raw = obj.raw_ai_response
        if not isinstance(raw, dict):
            return {}
        normalized = raw.get("normalized_exercise")
        return normalized if isinstance(normalized, dict) else {}

    def get_solution_strategy(self, obj) -> str:
        return str(self._normalized(obj).get("solution_strategy") or "")

    def get_solution_explanation(self, obj) -> str:
        return str(self._normalized(obj).get("solution_explanation") or "")

    def get_common_mistakes(self, obj) -> list:
        value = self._normalized(obj).get("common_mistakes", [])
        if isinstance(value, list):
            return value
        return []

    def get_alternative_method(self, obj) -> str:
        return str(self._normalized(obj).get("alternative_method") or "")

    def get_reference_question_ids(self, obj) -> list[int]:
        raw = obj.raw_ai_response if isinstance(obj.raw_ai_response, dict) else {}
        value = self._normalized(obj).get(
            "reference_question_ids",
            raw.get("reference_question_ids", []),
        )
        if not isinstance(value, list):
            return []

        result = []
        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result
