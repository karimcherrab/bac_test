from django.db import transaction
from django.utils import timezone

from adaptive_assessment.models import AdaptiveTest, AdaptiveTestQuestion
from adaptive_assessment.services.context_builder import QuestionContextBuilder
from adaptive_assessment.services.groq_generator import (
    GroqQuestionGenerationError,
    GroqQuestionGenerator,
)
from adaptive_assessment.services.question_validator import QuestionValidator


class QuestionGenerationFailed(RuntimeError):
    pass


class AdaptiveTestBuilder:
    """Generate ONE question at a time for the blueprint cursor."""

    MAX_VALIDATION_ATTEMPTS = 3

    def __init__(self, generator=None, validator=None):
        self.generator = generator or GroqQuestionGenerator()
        self.validator = validator or QuestionValidator()

    @staticmethod
    def _runtime(test):
        blueprint = dict(test.blueprint or {})
        runtime = dict(blueprint.get("runtime") or {})
        runtime.setdefault("cursor_index", 0)
        runtime.setdefault("generated_attempts", 0)
        runtime.setdefault("completed_targets", 0)
        runtime.setdefault("attempts_by_target", {})
        blueprint["runtime"] = runtime
        return blueprint, runtime

    @staticmethod
    def _slot_key(slot):
        if slot.get("source_type") == "skill":
            return f"skill:{slot.get('skill_id')}:{slot.get('skill_idea_code')}"
        return f"bac:{slot.get('bac_idea_id')}:{slot.get('variant_id') or 'idea'}"

    def start_test(self, test: AdaptiveTest):
        slots = list((test.blueprint or {}).get("slots") or [])
        if not slots:
            # Nothing left means the axis is already mastered.
            test.status = "completed"
            test.score = 100.0
            test.mastery_score = 100.0
            test.completed_at = timezone.now()
            test.save(update_fields=["status", "score", "mastery_score", "completed_at", "updated_at"])
            return test

        # A fresh test must not contain old generated questions.
        AdaptiveTestQuestion.objects.filter(test=test).delete()
        return self.ensure_current_question(test)

    def ensure_current_question(self, test: AdaptiveTest, *, force_new=False, retry_reason=""):
        test.refresh_from_db()
        blueprint, runtime = self._runtime(test)
        slots = list(blueprint.get("slots") or [])
        cursor = int(runtime.get("cursor_index") or 0)

        if cursor >= len(slots):
            self._complete_test(test, blueprint)
            return test

        # If an unanswered question already exists for the current cursor, reuse it.
        if not force_new:
            unanswered = (
                test.test_questions.filter(answer__isnull=True, is_validated=True)
                .order_by("-order")
                .first()
            )
            if unanswered is not None:
                if test.status in {"draft", "ready"}:
                    test.status = "in_progress"
                    if not test.started_at:
                        test.started_at = timezone.now()
                    test.save(update_fields=["status", "started_at", "updated_at"])
                return test

        slot = slots[cursor]
        generated, report = self._generate_valid_question(slot, retry_reason=retry_reason)

        with transaction.atomic():
            locked = AdaptiveTest.objects.select_for_update().get(pk=test.pk)
            blueprint, runtime = self._runtime(locked)
            # Guard against a duplicate generator call after another request advanced cursor.
            if int(runtime.get("cursor_index") or 0) != cursor:
                return locked

            next_order = (
                locked.test_questions.order_by("-order").values_list("order", flat=True).first()
                or 0
            ) + 1

            AdaptiveTestQuestion.objects.create(
                test=locked,
                order=next_order,
                source_type=slot["source_type"],
                skill_id=slot.get("skill_id"),
                bac_idea_id=slot.get("bac_idea_id"),
                variant_id=slot.get("variant_id"),
                target_skill_idea_codes=slot.get("target_skill_idea_codes", []),
                target_misconception_codes=slot.get("target_misconception_codes", []),
                difficulty=slot["difficulty"],
                question=generated,
                generation_model=self.generator.model,
                validation_report={
                    **report.to_dict(),
                    "sequence_target_index": cursor,
                    "sequence_target_order": cursor + 1,
                    "sequence_target_key": self._slot_key(slot),
                },
                is_validated=True,
            )

            key = self._slot_key(slot)
            attempts = dict(runtime.get("attempts_by_target") or {})
            attempts[key] = int(attempts.get(key) or 0) + 1
            runtime["attempts_by_target"] = attempts
            runtime["generated_attempts"] = int(runtime.get("generated_attempts") or 0) + 1
            blueprint["runtime"] = runtime
            locked.blueprint = blueprint
            locked.status = "in_progress"
            if not locked.started_at:
                locked.started_at = timezone.now()
            locked.save(update_fields=["blueprint", "status", "started_at", "updated_at"])
            return locked

    def advance_after_answer(self, test: AdaptiveTest, *, was_correct: bool):
        """
        Update only the deterministic sequence state.

        IMPORTANT: do NOT call Groq here. Correction and next-question generation
        are deliberately separated to reduce TPM pressure. The UI calls
        /tests/<id>/next/ only after the student has read the feedback.
        """
        with transaction.atomic():
            locked = AdaptiveTest.objects.select_for_update().get(pk=test.pk)
            blueprint, runtime = self._runtime(locked)
            slots = list(blueprint.get("slots") or [])
            cursor = int(runtime.get("cursor_index") or 0)

            if was_correct:
                cursor += 1
                runtime["cursor_index"] = cursor
                runtime["completed_targets"] = cursor
                blueprint["runtime"] = runtime
                locked.blueprint = blueprint
                progress_score = round((cursor / max(len(slots), 1)) * 100.0, 2)
                locked.score = progress_score
                locked.mastery_score = progress_score

                if cursor >= len(slots):
                    locked.status = "completed"
                    locked.score = 100.0
                    locked.mastery_score = 100.0
                    locked.completed_at = timezone.now()
                    locked.save(
                        update_fields=[
                            "blueprint",
                            "status",
                            "score",
                            "mastery_score",
                            "completed_at",
                            "updated_at",
                        ]
                    )
                    return locked

                locked.save(
                    update_fields=["blueprint", "score", "mastery_score", "updated_at"]
                )
            else:
                # Wrong/partial answer: stay on the exact same target.
                blueprint["runtime"] = runtime
                locked.blueprint = blueprint
                locked.status = "in_progress"
                locked.save(update_fields=["blueprint", "status", "updated_at"])

            return locked

    def _generate_valid_question(self, slot, *, retry_reason=""):
        source, context = QuestionContextBuilder.for_slot(slot)
        retry_feedback = None
        if retry_reason:
            retry_feedback = {"instruction": retry_reason}

        last_report = None
        try:
            for _ in range(self.MAX_VALIDATION_ATTEMPTS):
                generated = self.generator.generate(
                    slot=slot,
                    source_context=context,
                    retry_feedback=retry_feedback,
                )
                last_report = self.validator.validate(generated, slot=slot, source=source)
                if last_report.valid:
                    return generated, last_report
                retry_feedback = last_report.to_dict()
        except GroqQuestionGenerationError as exc:
            raise QuestionGenerationFailed(str(exc)) from exc
        except Exception as exc:
            raise QuestionGenerationFailed(
                "تعذر تحضير التمرين حالياً بسبب خدمة الذكاء الاصطناعي. أعد المحاولة."
            ) from exc

        raise QuestionGenerationFailed(
            "تعذر إنشاء تمرين صالح لهذه الفكرة بعد محاولات التحقق."
            + (f" {last_report.errors}" if last_report else "")
        )

    @staticmethod
    def _complete_test(test, blueprint):
        runtime = dict((blueprint or {}).get("runtime") or {})
        slots = list((blueprint or {}).get("slots") or [])
        runtime["cursor_index"] = len(slots)
        runtime["completed_targets"] = len(slots)
        blueprint["runtime"] = runtime
        test.blueprint = blueprint
        test.status = "completed"
        test.score = 100.0
        test.mastery_score = 100.0
        test.completed_at = timezone.now()
        test.save(
            update_fields=[
                "blueprint",
                "status",
                "score",
                "mastery_score",
                "completed_at",
                "updated_at",
            ]
        )
