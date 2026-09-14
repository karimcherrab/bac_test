from adaptive_assessment.models import BacIdea, Skill


def _short(value, limit=1200):
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _compact_list(value, max_items=10):
    if not isinstance(value, list):
        return []
    return value[:max_items]


class QuestionContextBuilder:
    """Build the smallest trustworthy context needed for one idea/question."""

    @staticmethod
    def for_slot(slot):
        source_type = slot.get("source_type")
        if source_type == "skill":
            return QuestionContextBuilder._for_skill(slot)
        if source_type == "bac":
            return QuestionContextBuilder._for_bac(slot)
        raise ValueError(f"Unsupported source_type: {source_type}")

    @staticmethod
    def _for_skill(slot):
        skill = Skill.objects.prefetch_related("misconceptions").get(
            pk=slot["skill_id"], is_active=True
        )
        target_code = str(slot.get("skill_idea_code") or "").strip()
        idea = next(
            (
                item
                for item in (skill.ideas or [])
                if isinstance(item, dict)
                and str(item.get("code") or "").strip() == target_code
            ),
            None,
        )
        if idea is None:
            raise ValueError("Selected lesson idea no longer exists in Skill.ideas.")

        misconceptions = []
        for item in skill.misconceptions.all():
            if not item.is_active:
                continue
            if item.related_skill_idea_codes and target_code not in (item.related_skill_idea_codes or []):
                continue
            misconceptions.append({
                "code": item.code,
                "description": _short(item.description, 350),
            })

        return skill, {
            "policy": "single_axis_lesson_idea",
            "skill": {
                "code": skill.code,
                "name": _short(skill.name, 180),
            },
            "lesson_idea": {
                "code": target_code,
                "name": _short(idea.get("name") or idea.get("title") or target_code, 220),
                "description": _short(idea.get("description"), 1000),
                "difficulty": idea.get("difficulty") or "medium",
            },
            "misconceptions": misconceptions[:6],
        }

    @staticmethod
    def _for_bac(slot):
        idea = BacIdea.objects.prefetch_related("variants", "misconceptions").get(
            pk=slot["bac_idea_id"], is_active=True
        )
        if int(idea.occurrence_count or 0) <= 0:
            raise ValueError("Selected BAC idea has no documented occurrence.")

        variant = None
        if slot.get("variant_id"):
            variant = next(
                (
                    item
                    for item in idea.variants.all()
                    if item.id == slot["variant_id"]
                    and item.is_active
                    and int(item.occurrence_count or 0) > 0
                ),
                None,
            )
            if variant is None:
                raise ValueError("Selected BAC variant has no documented occurrence.")

        # Years, occurrence arrays and historical subjects stay in DB/blueprint
        # for the UI. The LLM only needs the pedagogical shape of this one idea.
        context = {
            "policy": "single_documented_bac_idea",
            "bac_idea": {
                "code": idea.code,
                "title": _short(idea.title, 240),
                "description": _short(idea.description, 1200),
                "difficulty_range": [idea.difficulty_min, idea.difficulty_max],
                "required_skills": _compact_list(idea.required_skills, 10),
                "prerequisites": _compact_list(idea.prerequisites, 8),
                "generation_guidance": idea.generation_guidance or {},
            },
            "variant": None,
            "misconceptions": [
                {"code": item.code, "description": _short(item.description, 350)}
                for item in idea.misconceptions.all()
                if item.is_active
            ][:6],
        }
        if variant:
            context["variant"] = {
                "code": variant.code,
                "title": _short(variant.title, 240),
                "description": _short(variant.description, 900),
                "difficulty": variant.difficulty,
                "required_skills": _compact_list(variant.required_skills, 10),
                "distinguishing_feature": _short(variant.distinguishing_feature, 700),
            }

        return idea, context
