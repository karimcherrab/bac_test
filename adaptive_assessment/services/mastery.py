import json
from django.db import transaction
from django.utils import timezone
from adaptive_assessment.models import StudentBacIdeaMastery, StudentSkillMastery


def _bounded_score(old_score, evidence, alpha=0.35):
    old_score = float(old_score or 0.0)
    evidence = max(0.0, min(float(evidence), 100.0))
    return round(old_score * (1 - alpha) + evidence * alpha, 2)


def _teacher_feedback(answer):
    raw = answer.feedback
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


@transaction.atomic
def update_mastery_from_answer(answer):
    q = answer.test_question
    evidence = float(answer.score) * 100.0
    now = timezone.now()
    teacher = _teacher_feedback(answer)

    if q.skill_id:
        mastery, _ = StudentSkillMastery.objects.select_for_update().get_or_create(
            student=answer.student,
            skill=q.skill,
        )
        mastery.attempts_count += 1
        mastery.correct_count += int(answer.is_correct)
        mastery.consecutive_successes = (
            mastery.consecutive_successes + 1 if answer.is_correct else 0
        )
        mastery.mastery_score = _bounded_score(mastery.mastery_score, evidence)

        mastered = set(mastery.mastered_idea_codes or [])
        weak = set(mastery.weak_idea_codes or [])
        targets = set(q.target_skill_idea_codes or [])

        reported_mastered = set(teacher.get("mastered_skill_idea_codes") or []) & targets
        reported_weak = set(teacher.get("weak_skill_idea_codes") or []) & targets

        # Current evidence for the target idea must override older evidence.
        if answer.is_correct:
            reported_mastered |= targets
            reported_weak -= targets
        else:
            reported_weak |= targets
            reported_mastered -= targets

        mastered.difference_update(reported_weak)
        weak.difference_update(reported_mastered)
        mastered.update(reported_mastered)
        weak.update(reported_weak)

        mastery.mastered_idea_codes = sorted(mastered)
        mastery.weak_idea_codes = sorted(weak)

        required = set(q.skill.idea_codes)
        mastery.is_mastered = bool(required) and required.issubset(mastered) and not (
            required & weak
        )
        mastery.last_attempt_at = now
        mastery.save()

    if q.bac_idea_id:
        mastery, _ = StudentBacIdeaMastery.objects.select_for_update().get_or_create(
            student=answer.student,
            bac_idea=q.bac_idea,
        )
        mastery.attempts_count += 1
        mastery.correct_count += int(answer.is_correct)
        mastery.consecutive_successes = (
            mastery.consecutive_successes + 1 if answer.is_correct else 0
        )
        mastery.mastery_score = _bounded_score(mastery.mastery_score, evidence)

        mastered = set(mastery.mastered_variant_codes or [])
        weak = set(mastery.weak_variant_codes or [])

        if q.variant_id:
            code = q.variant.code
            if answer.is_correct:
                mastered.add(code)
                weak.discard(code)
            else:
                weak.add(code)
                mastered.discard(code)

        detected = set(mastery.detected_misconception_codes or [])
        detected.update(answer.detected_misconception_codes or [])
        mastery.mastered_variant_codes = sorted(mastered)
        mastery.weak_variant_codes = sorted(weak)
        mastery.detected_misconception_codes = sorted(detected)

        documented_variants = {
            v.code for v in q.bac_idea.variants.all()
            if v.is_active and int(v.occurrence_count or 0) > 0
        }
        if documented_variants:
            mastery.is_mastered = documented_variants.issubset(mastered) and not (
                documented_variants & weak
            )
        else:
            # For a BAC idea with no variant rows, the question itself is the idea.
            mastery.is_mastered = bool(answer.is_correct)

        mastery.last_attempt_at = now
        mastery.save()
