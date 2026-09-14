import json

from rest_framework import serializers

from .models import (
    AdaptiveAnswer,
    AdaptiveTest,
    AdaptiveTestQuestion,
    BacIdea,
    BacIdeaVariant,
    Misconception,
    Skill,
    StudentBacIdeaMastery,
    StudentSkillMastery,
)
from .services.bac_context import get_axis_bac_ideas


def _teacher_feedback(answer):
    if not answer:
        return {}

    raw = answer.feedback
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}

    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {"teacher_message": str(raw)}


def _skill_idea_map(skill):
    if not skill:
        return {}

    result = {}
    for item in (skill.ideas or []):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        result[code] = {
            "code": code,
            "name": item.get("name") or item.get("title") or code,
            "description": item.get("description") or "",
            "difficulty": item.get("difficulty") or "",
        }
    return result


def _question_target_ideas(question):
    idea_map = _skill_idea_map(question.skill)
    output = []

    for code in (question.target_skill_idea_codes or []):
        code = str(code)
        item = idea_map.get(code)
        if item:
            output.append(item)
        else:
            output.append({
                "code": code,
                "name": code,
                "description": "",
                "difficulty": "",
            })

    return output


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = "__all__"


class BacIdeaVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacIdeaVariant
        fields = "__all__"


class MisconceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Misconception
        fields = "__all__"


class BacIdeaSerializer(serializers.ModelSerializer):
    variants = BacIdeaVariantSerializer(many=True, read_only=True)
    misconceptions = MisconceptionSerializer(many=True, read_only=True)

    class Meta:
        model = BacIdea
        fields = "__all__"


class StudentSkillMasterySerializer(serializers.ModelSerializer):
    skill_code = serializers.CharField(source="skill.code", read_only=True)
    skill_name = serializers.CharField(source="skill.name", read_only=True)
    weak_ideas = serializers.SerializerMethodField()
    mastered_ideas = serializers.SerializerMethodField()

    class Meta:
        model = StudentSkillMastery
        fields = "__all__"

    def get_weak_ideas(self, obj):
        mapping = _skill_idea_map(obj.skill)
        return [
            mapping.get(code, {"code": code, "name": code, "description": ""})
            for code in (obj.weak_idea_codes or [])
        ]

    def get_mastered_ideas(self, obj):
        mapping = _skill_idea_map(obj.skill)
        return [
            mapping.get(code, {"code": code, "name": code, "description": ""})
            for code in (obj.mastered_idea_codes or [])
        ]


class StudentBacIdeaMasterySerializer(serializers.ModelSerializer):
    bac_idea_code = serializers.CharField(source="bac_idea.code", read_only=True)
    bac_idea_title = serializers.CharField(source="bac_idea.title", read_only=True)

    class Meta:
        model = StudentBacIdeaMastery
        fields = "__all__"


class AdaptiveAnswerSerializer(serializers.ModelSerializer):
    teacher_feedback = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    max_score = serializers.SerializerMethodField()
    answer_mode = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = AdaptiveAnswer
        fields = "__all__"

    def get_teacher_feedback(self, obj):
        return _teacher_feedback(obj)

    def get_percentage(self, obj):
        return round(float(obj.score or 0.0) * 100, 2)

    def get_max_score(self, obj):
        return 1.0

    def get_answer_mode(self, obj):
        payload = obj.answer if isinstance(obj.answer, dict) else {}
        return "image" if payload.get("format") == "image_solution" else "written"

    def get_image_count(self, obj):
        payload = obj.answer if isinstance(obj.answer, dict) else {}
        images = payload.get("images") or []
        return len(images) if isinstance(images, list) else 0


class AdaptiveTestQuestionSerializer(serializers.ModelSerializer):
    answer = AdaptiveAnswerSerializer(read_only=True)

    # Keep codes for backend/debugging, but the UI should use the Arabic labels below.
    skill_code = serializers.CharField(source="skill.code", read_only=True, default="")
    skill_name = serializers.CharField(source="skill.name", read_only=True, default="")
    skill_description = serializers.CharField(
        source="skill.description", read_only=True, default=""
    )

    bac_idea_code = serializers.CharField(
        source="bac_idea.code", read_only=True, default=""
    )
    bac_idea_title = serializers.CharField(
        source="bac_idea.title", read_only=True, default=""
    )
    bac_idea_description = serializers.CharField(
        source="bac_idea.description", read_only=True, default=""
    )

    variant_code = serializers.CharField(source="variant.code", read_only=True, default="")
    variant_title = serializers.CharField(
        source="variant.title", read_only=True, default=""
    )
    variant_description = serializers.CharField(
        source="variant.description", read_only=True, default=""
    )

    target_skill_ideas = serializers.SerializerMethodField()
    concept_label = serializers.SerializerMethodField()
    bac_idea_years = serializers.SerializerMethodField()
    bac_idea_occurrence_count = serializers.SerializerMethodField()
    variant_years = serializers.SerializerMethodField()
    variant_occurrence_count = serializers.SerializerMethodField()
    historical_years = serializers.SerializerMethodField()
    historical_occurrence_count = serializers.SerializerMethodField()

    class Meta:
        model = AdaptiveTestQuestion
        fields = "__all__"

    def get_target_skill_ideas(self, obj):
        return _question_target_ideas(obj)

    def get_concept_label(self, obj):
        if obj.source_type == "skill" and obj.skill_id:
            targets = _question_target_ideas(obj)
            if targets:
                return targets[0].get("name") or targets[0].get("code")
            return obj.skill.name
        if obj.bac_idea_id:
            if obj.variant_id and obj.variant.title:
                return obj.variant.title
            return obj.bac_idea.title
        return "فكرة من المحور"

    def get_bac_idea_years(self, obj):
        return list(obj.bac_idea.years or []) if obj.bac_idea_id else []

    def get_bac_idea_occurrence_count(self, obj):
        return int(obj.bac_idea.occurrence_count or 0) if obj.bac_idea_id else 0

    def get_variant_years(self, obj):
        return list(obj.variant.years or []) if obj.variant_id else []

    def get_variant_occurrence_count(self, obj):
        return int(obj.variant.occurrence_count or 0) if obj.variant_id else 0

    def get_historical_years(self, obj):
        if obj.variant_id and obj.variant.years:
            return list(obj.variant.years or [])
        return self.get_bac_idea_years(obj)

    def get_historical_occurrence_count(self, obj):
        if obj.variant_id and int(obj.variant.occurrence_count or 0) > 0:
            return int(obj.variant.occurrence_count or 0)
        return self.get_bac_idea_occurrence_count(obj)


class AdaptiveTestHistorySerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()
    correct_count = serializers.SerializerMethodField()
    axis_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()

    class Meta:
        model = AdaptiveTest
        fields = [
            "id",
            "axis",
            "axis_name",
            "branch",
            "branch_name",
            "mode",
            "status",
            "score",
            "mastery_score",
            "created_at",
            "started_at",
            "completed_at",
            "question_count",
            "answered_count",
            "correct_count",
        ]

    def get_axis_name(self, obj):
        return str(obj.axis) if obj.axis_id else ""

    def get_branch_name(self, obj):
        return str(obj.branch) if obj.branch_id else ""

    def get_question_count(self, obj):
        value = getattr(obj, "question_count_value", None)
        if value is not None:
            return value
        return obj.test_questions.count()

    def get_answered_count(self, obj):
        value = getattr(obj, "answered_count_value", None)
        if value is not None:
            return value
        return obj.test_questions.filter(answer__isnull=False).count()

    def get_correct_count(self, obj):
        value = getattr(obj, "correct_count_value", None)
        if value is not None:
            return value
        return obj.test_questions.filter(answer__is_correct=True).count()


class AdaptiveTestSerializer(serializers.ModelSerializer):
    test_questions = AdaptiveTestQuestionSerializer(many=True, read_only=True)
    bac_ideas = serializers.SerializerMethodField()
    axis_ideas = serializers.SerializerMethodField()
    learning_summary = serializers.SerializerMethodField()
    mastery_summary = serializers.SerializerMethodField()

    class Meta:
        model = AdaptiveTest
        fields = "__all__"

    def get_bac_ideas(self, obj):
        if not obj.axis_id or not obj.branch_id:
            return []
        return get_axis_bac_ideas(axis=obj.axis, branch=obj.branch)

    def get_axis_ideas(self, obj):
        output = []
        for skill in obj.axis.assessment_skills.filter(is_active=True).order_by("order", "id"):
            for idea in (skill.ideas or []):
                if not isinstance(idea, dict) or not idea.get("code"):
                    continue
                output.append({
                    "type": "lesson",
                    "skill_id": skill.id,
                    "skill_code": skill.code,
                    "skill_name": skill.name,
                    "code": idea.get("code"),
                    "title": idea.get("name") or idea.get("title") or idea.get("code"),
                    "description": idea.get("description") or "",
                    "difficulty": idea.get("difficulty") or "medium",
                })
        return output

    def get_learning_summary(self, obj):
        """Summarize CURRENT target mastery, not every retry attempt."""
        latest_by_target = {}
        for question in obj.test_questions.all():
            report = question.validation_report or {}
            key = report.get("sequence_target_key")
            if not key:
                if question.source_type == "skill":
                    code = (question.target_skill_idea_codes or [""])[0]
                    key = f"skill:{question.skill_id}:{code}"
                else:
                    key = f"bac:{question.bac_idea_id}:{question.variant_id or 'idea'}"
            latest_by_target[key] = question

        mastered = []
        review = []
        for question in latest_by_target.values():
            answer = getattr(question, "answer", None)
            is_mastered = bool(answer and answer.is_correct)

            if question.source_type == "skill":
                targets = _question_target_ideas(question)
                idea = targets[0] if targets else {}
                item = {
                    "type": "lesson",
                    "code": idea.get("code") or "",
                    "title": (idea.get("name") or (question.skill.name if question.skill_id else "فكرة من المحور")),
                    "description": idea.get("description") or "",
                    "skill_name": question.skill.name if question.skill_id else "",
                    "reason": "فكرة أساسية من المحور",
                    "years": [],
                    "occurrence_count": 0,
                }
            else:
                years = (
                    list(question.variant.years or [])
                    if question.variant_id and question.variant.years
                    else list(question.bac_idea.years or [])
                )
                count = (
                    int(question.variant.occurrence_count or 0)
                    if question.variant_id and int(question.variant.occurrence_count or 0) > 0
                    else int(question.bac_idea.occurrence_count or 0)
                )
                item = {
                    "type": "bac",
                    "code": question.variant.code if question.variant_id else question.bac_idea.code,
                    "title": question.variant.title if question.variant_id else question.bac_idea.title,
                    "parent_title": question.bac_idea.title,
                    "description": (
                        question.variant.description
                        if question.variant_id and question.variant.description
                        else question.bac_idea.description
                    ),
                    "reason": "فكرة موثقة في البكالوريا",
                    "years": years,
                    "occurrence_count": count,
                }

            (mastered if is_mastered else review).append(item)

        return {
            "mastered_concepts": mastered,
            "review_concepts": review,
            "correct_concepts": mastered,
            "similar_practice": [],
        }

    def get_mastery_summary(self, obj):
        blueprint = obj.blueprint or {}
        slots = list(blueprint.get("slots") or [])
        runtime = dict(blueprint.get("runtime") or {})
        completed = min(int(runtime.get("completed_targets") or runtime.get("cursor_index") or 0), len(slots))
        return {
            "total_targets": len(slots),
            "answered_targets": completed,
            "mastered_targets": completed,
            "remaining_targets": max(len(slots) - completed, 0),
            "axis_mastered": bool(slots) and completed >= len(slots),
            "needs_retest": completed < len(slots),
            "generated_attempts": int(runtime.get("generated_attempts") or 0),
        }
