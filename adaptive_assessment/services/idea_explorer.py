from django.db.models import Prefetch

from adaptive_assessment.models import (
    BacIdea,
    BacIdeaVariant,
    StudentBacIdeaMastery,
)
from adaptive_assessment.services.blueprint import BlueprintGenerator


PRIORITY_WEIGHT = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.55,
    "low": 0.3,
}

FREQUENCY_LABEL_AR = {
    "very_high": "متكررة جدًا",
    "high": "متكررة",
    "medium": "متوسطة التكرار",
    "low": "قليلة التكرار",
    "rare": "نادرة",
}

PRIORITY_LABEL_AR = {
    "critical": "أولوية قصوى",
    "high": "أولوية عالية",
    "medium": "أولوية متوسطة",
    "low": "أولوية منخفضة",
}


class IdeaExplorerService:
    """
    Read-only dashboard data for documented BAC ideas + one-target practice blueprint.

    Historical statistics come only from BacIdea/BacIdeaVariant stored data. The service
    does not invent BAC probabilities or extrapolate undocumented years.
    """

    @staticmethod
    def _clean_years(values):
        years = []
        for raw in values or []:
            text = str(raw or "").strip()
            if not text:
                continue
            try:
                year = int(text)
                if 1990 <= year <= 2100:
                    years.append(year)
                else:
                    years.append(text)
            except (TypeError, ValueError):
                years.append(text)
        # Keep unique values and sort numerical years descending first.
        unique = list(dict.fromkeys(years))
        numeric = sorted([y for y in unique if isinstance(y, int)], reverse=True)
        other = [y for y in unique if not isinstance(y, int)]
        return numeric + other

    @staticmethod
    def _normalize_occurrence(raw):
        if not isinstance(raw, dict):
            return None

        def pick(*keys):
            for key in keys:
                value = raw.get(key)
                if value not in (None, "", []):
                    return value
            return ""

        return {
            "year": pick("year", "bac_year", "annee", "السنة"),
            "session": pick("session", "session_type", "type", "الدورة"),
            "subject": pick("subject", "subject_name", "sujet", "الموضوع"),
            "exercise": pick("exercise", "exercise_number", "exercise_no", "التمرين"),
            "question": pick("question", "question_number", "question_no", "السؤال"),
            "source_file": pick("source_file", "file", "filename", "source"),
        }

    def dashboard(self, *, student, axis, branch):
        variants_qs = BacIdeaVariant.objects.filter(
            is_active=True,
            occurrence_count__gt=0,
        ).order_by("difficulty", "code")

        ideas = list(
            BacIdea.objects.filter(
                axis=axis,
                branch=branch,
                is_active=True,
                occurrence_count__gt=0,
            )
            .prefetch_related(
                Prefetch("variants", queryset=variants_qs),
                "misconceptions",
            )
            .order_by("code")
        )

        masteries = {
            row.bac_idea_id: row
            for row in StudentBacIdeaMastery.objects.filter(
                student=student,
                bac_idea__axis=axis,
                bac_idea__branch=branch,
            )
        }

        total_occurrences = sum(int(idea.occurrence_count or 0) for idea in ideas)
        max_occurrence = max([int(idea.occurrence_count or 0) for idea in ideas] or [1])
        mastered_count = 0
        attempted_count = 0
        weak_count = 0
        mastery_values = []
        cards = []

        for idea in ideas:
            mastery = masteries.get(idea.id)
            mastery_score = round(float(mastery.mastery_score or 0.0), 1) if mastery else 0.0
            attempts = int(mastery.attempts_count or 0) if mastery else 0
            correct = int(mastery.correct_count or 0) if mastery else 0
            mastered_codes = set(mastery.mastered_variant_codes or []) if mastery else set()
            weak_codes = set(mastery.weak_variant_codes or []) if mastery else set()

            if mastery and mastery.is_mastered:
                status_key = "mastered"
                mastered_count += 1
            elif weak_codes or (attempts > 0 and mastery_score < 70):
                status_key = "weak"
                weak_count += 1
            elif attempts > 0:
                status_key = "in_progress"
            else:
                status_key = "new"

            if attempts > 0:
                attempted_count += 1
                mastery_values.append(mastery_score)

            frequency_ratio = int(idea.occurrence_count or 0) / max(max_occurrence, 1)
            weakness_ratio = 1.0 - min(max(mastery_score, 0.0), 100.0) / 100.0
            priority_ratio = PRIORITY_WEIGHT.get(idea.priority, 0.5)
            practice_score = round(
                min(100.0, frequency_ratio * 55 + weakness_ratio * 35 + priority_ratio * 10),
                1,
            )
            # A mastered idea stays available for review, but weak/new ideas should
            # naturally rise above it in the recommended-practice ranking.
            if status_key == "mastered":
                practice_score = round(practice_score * 0.35, 1)

            if status_key == "mastered":
                recommendation = "مراجعة تثبيت"
            elif practice_score >= 75:
                recommendation = "ابدأ بها الآن"
            elif practice_score >= 55:
                recommendation = "مهمة جدًا"
            else:
                recommendation = "تدرّب عليها لاحقًا"

            variant_cards = []
            variants = list(idea.variants.all())
            for variant in variants:
                if variant.code in mastered_codes and variant.code not in weak_codes:
                    variant_state = "mastered"
                elif variant.code in weak_codes:
                    variant_state = "weak"
                else:
                    variant_state = "new"
                variant_cards.append(
                    {
                        "id": variant.id,
                        "code": variant.code,
                        "title": variant.title,
                        "description": variant.description,
                        "years": self._clean_years(variant.years),
                        "occurrence_count": int(variant.occurrence_count or 0),
                        "difficulty": int(variant.difficulty or 1),
                        "state": variant_state,
                        "distinguishing_feature": variant.distinguishing_feature,
                    }
                )

            occurrence_cards = []
            for raw in (idea.bac_occurrences or [])[:30]:
                normalized = self._normalize_occurrence(raw)
                if normalized:
                    occurrence_cards.append(normalized)

            years = self._clean_years(idea.years)
            cards.append(
                {
                    "id": idea.id,
                    "code": idea.code,
                    "title": idea.title,
                    "description": idea.description,
                    "priority": idea.priority,
                    "priority_label": PRIORITY_LABEL_AR.get(idea.priority, idea.priority),
                    "frequency_level": idea.frequency_level,
                    "frequency_label": FREQUENCY_LABEL_AR.get(
                        idea.frequency_level, idea.frequency_level
                    ),
                    "occurrence_count": int(idea.occurrence_count or 0),
                    "years": years,
                    "first_documented_year": years[-1] if years else None,
                    "last_documented_year": years[0] if years else None,
                    "difficulty_min": int(idea.difficulty_min or 1),
                    "difficulty_max": int(idea.difficulty_max or 3),
                    "required_skills": idea.required_skills or [],
                    "variants": variant_cards,
                    "bac_occurrences": occurrence_cards,
                    "appearance_share": round(
                        (int(idea.occurrence_count or 0) / max(total_occurrences, 1)) * 100,
                        1,
                    ),
                    "relative_frequency": round(frequency_ratio * 100, 1),
                    "practice_priority_score": practice_score,
                    "recommendation": recommendation,
                    "student": {
                        "status": status_key,
                        "mastery_score": mastery_score,
                        "attempts_count": attempts,
                        "correct_count": correct,
                        "success_rate": round((correct / max(attempts, 1)) * 100, 1)
                        if attempts
                        else 0.0,
                        "is_mastered": bool(mastery and mastery.is_mastered),
                        "mastered_variant_codes": sorted(mastered_codes),
                        "weak_variant_codes": sorted(weak_codes),
                        "detected_misconception_codes": (
                            mastery.detected_misconception_codes or [] if mastery else []
                        ),
                    },
                }
            )

        cards.sort(
            key=lambda item: (
                -float(item["practice_priority_score"]),
                -int(item["occurrence_count"]),
                item["code"],
            )
        )

        average_mastery = (
            round(sum(mastery_values) / len(mastery_values), 1) if mastery_values else 0.0
        )

        return {
            "axis_id": axis.pk,
            "branch_id": branch.pk,
            "summary": {
                "ideas_count": len(cards),
                "total_documented_occurrences": total_occurrences,
                "mastered_ideas": mastered_count,
                "attempted_ideas": attempted_count,
                "weak_ideas": weak_count,
                "average_mastery": average_mastery,
                "coverage_percentage": round(
                    (mastered_count / max(len(cards), 1)) * 100.0,
                    1,
                ),
            },
            "ideas": cards,
            "methodology_note": (
                "التكرار والسنوات مأخوذة من بيانات البكالوريا الموثقة المخزنة في المنصة؛ "
                "لا تمثل تنبؤًا باحتمال ظهور الفكرة مستقبلًا."
            ),
        }

    def build_practice_blueprint(self, *, student, axis, branch, idea, variant_id=None):
        # The idea is already scoped to axis/branch by the caller.
        variants = [
            item
            for item in idea.variants.all()
            if item.is_active and int(item.occurrence_count or 0) > 0
        ]
        mastery = StudentBacIdeaMastery.objects.filter(
            student=student,
            bac_idea=idea,
        ).first()

        selected = None
        if variant_id not in (None, ""):
            try:
                wanted = int(variant_id)
            except (TypeError, ValueError):
                raise ValueError("variant_id غير صالح.")
            selected = next((item for item in variants if item.id == wanted), None)
            if selected is None:
                raise ValueError("النوع المختار لا ينتمي إلى هذه الفكرة أو ليس موثقًا في البكالوريا.")
        elif variants:
            mastered = set(mastery.mastered_variant_codes or []) if mastery else set()
            weak = set(mastery.weak_variant_codes or []) if mastery else set()

            # 1) revisit a known weak variant first
            selected = next((item for item in variants if item.code in weak), None)
            # 2) otherwise choose the easiest not-yet-mastered documented variant
            if selected is None:
                selected = next((item for item in variants if item.code not in mastered), None)
            # 3) fully mastered idea: choose a high-frequency variant for spaced review
            if selected is None:
                selected = sorted(
                    variants,
                    key=lambda item: (-int(item.occurrence_count or 0), int(item.difficulty or 1)),
                )[0]

        slot = BlueprintGenerator._make_bac_slot(
            idea,
            selected,
            "manual_idea_practice",
        ).to_dict()
        slot["order"] = 1

        return {
            "version": "1.0-idea-practice",
            "mode": "idea_practice",
            "axis_id": axis.pk,
            "branch_id": branch.pk,
            "student_id": student.pk,
            "source_policy": "one_user_selected_documented_bac_idea",
            "sequence_policy": "retry_same_target_until_mastered",
            "coverage": {
                "lesson_ideas": 0,
                "bac_ideas": 1,
                "total_targets": 1,
            },
            "focus": {
                "bac_idea_id": idea.id,
                "bac_idea_code": idea.code,
                "bac_idea_title": idea.title,
                "variant_id": selected.id if selected else None,
                "variant_code": selected.code if selected else "",
                "variant_title": selected.title if selected else "",
            },
            "runtime": {
                "cursor_index": 0,
                "generated_attempts": 0,
                "completed_targets": 0,
                "attempts_by_target": {},
            },
            "slots": [slot],
        }
