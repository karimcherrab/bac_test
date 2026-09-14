from dataclasses import asdict, dataclass
from typing import Optional

from django.db.models import Prefetch

from adaptive_assessment.models import (
    BacIdea,
    BacIdeaVariant,
    Skill,
    StudentBacIdeaMastery,
    StudentSkillMastery,
)


DIFFICULTY_MAP = {"easy": 1, "medium": 2, "hard": 3}


@dataclass
class BlueprintSlot:
    order: int
    source_type: str
    difficulty: int
    skill_id: Optional[int] = None
    skill_code: str = ""
    skill_idea_code: str = ""
    skill_idea_name: str = ""
    skill_idea_description: str = ""
    bac_idea_id: Optional[int] = None
    bac_idea_code: str = ""
    bac_idea_title: str = ""
    variant_id: Optional[int] = None
    variant_code: str = ""
    variant_title: str = ""
    target_skill_idea_codes: list = None
    target_misconception_codes: list = None
    reason: str = ""
    bac_years: list = None
    bac_occurrence_count: int = 0
    variant_years: list = None
    variant_occurrence_count: int = 0

    def to_dict(self):
        data = asdict(self)
        for key in (
            "target_skill_idea_codes",
            "target_misconception_codes",
            "bac_years",
            "variant_years",
        ):
            data[key] = data.get(key) or []
        return data


class BlueprintGenerator:
    """
    Sequential mastery planner.

    - Every lesson idea in Skill.ideas is included.
    - Every documented BAC variant is included; when a BacIdea has no variant,
      the BacIdea itself is included.
    - Targets are sorted from easiest to hardest.
    - No max_questions truncation is ever applied.
    - Previously mastered targets are skipped only on later runs.
    - Runtime cursor lives in AdaptiveTest.blueprint, so no migration is needed.
    """

    def __init__(self, *, student, axis, branch, max_questions=None):
        self.student = student
        self.axis = axis
        self.branch = branch
        # Kept only for backward API compatibility. Intentionally ignored.
        self.max_questions = None

    def build(self):
        skills = list(
            Skill.objects.filter(axis=self.axis, is_active=True)
            .prefetch_related("misconceptions")
            .order_by("order", "id")
        )

        historical_variants = BacIdeaVariant.objects.filter(
            is_active=True,
            occurrence_count__gt=0,
        ).order_by("difficulty", "id")

        bac_ideas = list(
            BacIdea.objects.filter(
                axis=self.axis,
                branch=self.branch,
                is_active=True,
                occurrence_count__gt=0,
            )
            .prefetch_related(
                Prefetch("variants", queryset=historical_variants),
                "misconceptions",
            )
            .order_by("code")
        )

        skill_masteries = {
            row.skill_id: row
            for row in StudentSkillMastery.objects.filter(
                student=self.student,
                skill__axis=self.axis,
            )
        }
        bac_masteries = {
            row.bac_idea_id: row
            for row in StudentBacIdeaMastery.objects.filter(
                student=self.student,
                bac_idea__axis=self.axis,
                bac_idea__branch=self.branch,
            )
        }

        lesson_slots = self._lesson_slots(skills, skill_masteries)
        bac_slots = self._bac_slots(bac_ideas, bac_masteries)
        slots = lesson_slots + bac_slots

        # Global order: easiest -> hardest. Deterministic tie-breakers keep the
        # same sequence for the same database state.
        slots.sort(key=self._sort_key)
        for index, slot in enumerate(slots, start=1):
            slot.order = index

        lesson_count = sum(1 for slot in slots if slot.source_type == "skill")
        bac_count = sum(1 for slot in slots if slot.source_type == "bac")

        return {
            "version": "4.0-sequential-mastery",
            "mode": "sequential",
            "axis_id": self.axis.pk,
            "branch_id": self.branch.pk,
            "student_id": self.student.pk,
            "source_policy": "all_unmastered_axis_ideas_plus_documented_bac",
            "sequence_policy": "easy_to_hard_one_target_at_a_time",
            "coverage": {
                "lesson_ideas": lesson_count,
                "bac_ideas": bac_count,
                "total_targets": len(slots),
            },
            "runtime": {
                "cursor_index": 0,
                "generated_attempts": 0,
                "completed_targets": 0,
                "attempts_by_target": {},
            },
            "slots": [slot.to_dict() for slot in slots],
        }

    def _lesson_slots(self, skills, masteries):
        slots = []
        for skill in skills:
            mastery = masteries.get(skill.id)
            mastered = set(mastery.mastered_idea_codes or []) if mastery else set()
            weak = set(mastery.weak_idea_codes or []) if mastery else set()

            for raw in skill.ideas or []:
                if not isinstance(raw, dict):
                    continue
                code = str(raw.get("code") or "").strip()
                if not code:
                    continue

                # A later sequential run should not retest already-mastered ideas.
                if code in mastered and code not in weak:
                    continue

                misconception_codes = []
                for item in skill.misconceptions.all():
                    if not item.is_active:
                        continue
                    related = set(item.related_skill_idea_codes or [])
                    if not related or code in related:
                        misconception_codes.append(item.code)

                slots.append(
                    BlueprintSlot(
                        order=0,
                        source_type="skill",
                        difficulty=DIFFICULTY_MAP.get(
                            str(raw.get("difficulty") or "medium").lower(), 2
                        ),
                        skill_id=skill.id,
                        skill_code=skill.code,
                        skill_idea_code=code,
                        skill_idea_name=raw.get("name") or raw.get("title") or code,
                        skill_idea_description=raw.get("description") or "",
                        target_skill_idea_codes=[code],
                        target_misconception_codes=misconception_codes,
                        reason="weak_lesson_idea" if code in weak else "unmastered_lesson_idea",
                    )
                )
        return slots

    def _bac_slots(self, ideas, masteries):
        slots = []
        for idea in ideas:
            mastery = masteries.get(idea.id)
            mastered_variants = set(mastery.mastered_variant_codes or []) if mastery else set()
            weak_variants = set(mastery.weak_variant_codes or []) if mastery else set()

            variants = [
                item
                for item in idea.variants.all()
                if item.is_active and int(item.occurrence_count or 0) > 0
            ]

            if variants:
                for variant in variants:
                    if variant.code in mastered_variants and variant.code not in weak_variants:
                        continue
                    slots.append(
                        self._make_bac_slot(
                            idea,
                            variant,
                            "weak_bac_variant"
                            if variant.code in weak_variants
                            else "unmastered_bac_variant",
                        )
                    )
            else:
                if mastery and mastery.is_mastered:
                    continue
                slots.append(self._make_bac_slot(idea, None, "unmastered_bac_idea"))
        return slots

    @staticmethod
    def _make_bac_slot(idea, variant, reason):
        misconception_codes = [
            item.code for item in idea.misconceptions.all() if item.is_active
        ]
        difficulty = variant.difficulty if variant else idea.difficulty_min
        return BlueprintSlot(
            order=0,
            source_type="bac",
            difficulty=max(1, min(int(difficulty or 1), 5)),
            bac_idea_id=idea.id,
            bac_idea_code=idea.code,
            bac_idea_title=idea.title,
            variant_id=variant.id if variant else None,
            variant_code=variant.code if variant else "",
            variant_title=variant.title if variant else "",
            target_misconception_codes=misconception_codes,
            reason=reason,
            bac_years=list(idea.years or []),
            bac_occurrence_count=int(idea.occurrence_count or 0),
            variant_years=list(variant.years or []) if variant else [],
            variant_occurrence_count=int(variant.occurrence_count or 0) if variant else 0,
        )

    @staticmethod
    def _sort_key(slot):
        # skill first only when difficulty ties, then stable semantic codes.
        source_rank = 0 if slot.source_type == "skill" else 1
        semantic_code = (
            slot.skill_idea_code
            if slot.source_type == "skill"
            else (slot.variant_code or slot.bac_idea_code)
        )
        return (
            int(slot.difficulty or 1),
            source_rank,
            slot.skill_code or slot.bac_idea_code or "",
            semantic_code or "",
        )
