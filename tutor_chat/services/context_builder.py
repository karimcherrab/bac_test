from statistics import mean

from django.apps import apps
from django.db.models import Q

from course.models import Axis, Question

try:
    from course.models import ReExplainStepHistory
except ImportError:  # pragma: no cover
    ReExplainStepHistory = None

from .utils import clean_text, compact_json, first_non_empty, parse_json_maybe


SECTION_LABELS = {
    "intro": "الشرح",
    "resume": "مراجعة المحور",
    "question_bac": "تمارين البكالوريا الخاصة بالمحور",
    "question_generate": "تمارين مولدة بالذكاء الاصطناعي",
    "bac": "تمارين البكالوريا الكاملة",
    "generete-bac": "تمارين شبيهة بالبكالوريا مولدة بالذكاء الاصطناعي",
}

EXERCISE_KIND_ALIASES = {
    "question_bac": "axis_question",
    "bac_question": "axis_question",
    "course_question": "axis_question",
    "question": "axis_question",
    "axis_question": "axis_question",
    "bac_exercise": "bac_exercise",
    "generated_exercise": "generated_axis_exercise",
    "generated_axis_exercise": "generated_axis_exercise",
    "generated_bac": "generated_bac_exercise",
    "generated_bac_exercise": "generated_bac_exercise",
    "adaptive_question": "adaptive_test_question",
    "assessment_question": "adaptive_test_question",
    "adaptive_test_question": "adaptive_test_question",
}


class TutorContextBuilder:
    """
    يبني سياقًا موثوقًا من قاعدة البيانات قدر الإمكان.

    React يحدد فقط: ما الذي يشاهده الطالب الآن؟
    Django يعيد التحقق من هوية الفصل/المحور/التمرين/السؤال/الخطوة
    ثم يجلب النص الحقيقي من قاعدة البيانات.
    """

    def __init__(self, *, student, chapter, page_context=None):
        self.student = student
        self.chapter = chapter
        self.page_context = page_context or {}

        # مصادر داخلية لا تُرسل مباشرة إلى النموذج.
        self._exercise_record = None
        self._exercise_payload = {}
        self._exercise_solution = {}
        self._resolved_question_payload = {}
        self._resolved_question_solution = {}

    def build(self):
        axis = self._resolve_axis()
        exercise = self._resolve_exercise(axis)
        question = self._resolve_question(exercise)
        step = self._resolve_step(exercise, question)

        learning_state = self._learning_state(axis)
        recent_mistakes = self._recent_mistakes(axis)
        recent_confusions = self._recent_confusions(axis, exercise)

        section_id = clean_text(self.page_context.get("section_id"), 100)
        section_title = clean_text(
            self.page_context.get("section_title")
            or SECTION_LABELS.get(section_id, ""),
            255,
        )

        selection = clean_text(self.page_context.get("selection"), 3000)
        visible_block = clean_text(self.page_context.get("visible_block"), 5000)

        view_state = self.page_context.get("view_state")
        if not isinstance(view_state, dict):
            view_state = {}
        view_state = {
            "solution_visible": bool(view_state.get("solution_visible", False)),
            "alternative_solution_visible": bool(
                view_state.get("alternative_solution_visible", False)
            ),
            "visible_hints": self._safe_int(view_state.get("visible_hints"), 0),
            "showing_reexplanation": bool(
                view_state.get("showing_reexplanation", False)
            ),
        }

        lesson_excerpt = ""
        if axis is not None:
            lesson_excerpt = compact_json(axis.content, 6500)

        return {
            "chapter": {
                "id": self.chapter.id,
                "code": getattr(self.chapter, "code", ""),
                "title": getattr(self.chapter, "title", ""),
                "subject": self._chapter_subject_name(),
            },
            "axis": (
                {
                    "id": axis.id,
                    "tag": axis.tag,
                    "title": axis.title,
                    "lesson_excerpt": lesson_excerpt,
                }
                if axis
                else None
            ),
            "section": {
                "id": section_id,
                "title": section_title,
            },
            "exercise": exercise,
            "question": question,
            "step": step,
            "view_state": view_state,
            "selection": selection,
            "visible_block": visible_block,
            "student_learning": learning_state,
            "recent_mistakes": recent_mistakes,
            "recent_confusions": recent_confusions,
        }

    # ------------------------------------------------------------------
    # Chapter / axis
    # ------------------------------------------------------------------

    def _chapter_subject_name(self):
        try:
            subject = getattr(self.chapter, "subject", None)
            return getattr(subject, "name", "") if subject else ""
        except Exception:
            return ""

    def _resolve_axis(self):
        axis_id = self.page_context.get("axis_id")
        if not axis_id:
            return None

        return (
            Axis.objects
            .select_related("chapter")
            .filter(
                id=axis_id,
                chapter=self.chapter,
                is_active=True,
            )
            .first()
        )

    # ------------------------------------------------------------------
    # Exercise resolution
    # ------------------------------------------------------------------

    def _resolve_exercise(self, axis):
        raw = self.page_context.get("exercise")
        if not isinstance(raw, dict):
            return None

        raw_kind = clean_text(raw.get("kind") or raw.get("type"), 80).lower()
        kind = EXERCISE_KIND_ALIASES.get(raw_kind, raw_kind)
        raw_id = raw.get("id")

        resolver_map = {
            "axis_question": self._resolve_course_question,
            "bac_exercise": self._resolve_bac_exercise,
            "generated_axis_exercise": self._resolve_generated_axis_exercise,
            "generated_bac_exercise": self._resolve_generated_bac_exercise,
            "adaptive_test_question": self._resolve_adaptive_question,
        }

        resolver = resolver_map.get(kind)
        if resolver is not None:
            resolved = resolver(raw_id=raw_id, axis=axis, kind=kind)
            if resolved:
                return resolved

        # Fallback UI: useful only when a legacy component has not yet sent a DB id.
        text = clean_text(
            first_non_empty(
                raw,
                "text",
                "statement",
                "standalone_text",
                "visible_text",
            ),
            6000,
        )
        title = clean_text(raw.get("title"), 255)
        code = clean_text(raw.get("code"), 180)

        if not any([raw_id, text, title, code]):
            return None

        return {
            "kind": kind or "visible_exercise",
            "id": str(raw_id)[:120] if raw_id is not None else "",
            "code": code,
            "title": title,
            "text": text,
            "difficulty": clean_text(raw.get("difficulty"), 30),
            "skill": clean_text(raw.get("skill"), 255),
            "verified": False,
        }

    def _resolve_course_question(self, *, raw_id, axis, kind=None):
        if not raw_id:
            return None

        pk = self._coerce_model_pk(Question, raw_id)
        if pk is None:
            return None

        question = (
            Question.objects
            .select_related("axis", "axis__chapter")
            .filter(
                id=pk,
                axis__chapter=self.chapter,
                is_active=True,
            )
            .first()
        )
        if not question:
            return None
        if axis is not None and question.axis_id != axis.id:
            return None

        self._exercise_record = question
        self._exercise_payload = self._model_json(question, "content")
        self._exercise_solution = self._model_json(question, "solution")

        return {
            "kind": "axis_question",
            "id": question.id,
            "code": getattr(question, "code", ""),
            "title": getattr(question, "title", ""),
            "text": clean_text(
                getattr(question, "standalone_text", "")
                or getattr(question, "text", ""),
                6500,
            ),
            "context": clean_text(getattr(question, "context", ""), 2500),
            "difficulty": getattr(question, "difficulty", ""),
            "skill": getattr(question, "skill", ""),
            "year": getattr(question, "year", None),
            "verified": True,
        }

    def _resolve_bac_exercise(self, *, raw_id, axis, kind=None):
        model = self._find_model(
            "ExerciseBac",
            preferred_labels=("exercise_bac", "bac_exercises"),
        )
        if model is None or not raw_id:
            return None
        pk = self._coerce_model_pk(model, raw_id)
        if pk is None:
            return None

        exercise = (
            model.objects
            .filter(
                id=pk,
                chapter=self.chapter,
                is_active=True,
            )
            .first()
        )
        if exercise is None:
            return None

        axis_tags = self._normalize_axis_tags(getattr(exercise, "axis_tags", []))
        if axis is not None and axis_tags and axis.tag not in axis_tags:
            return None

        self._exercise_record = exercise
        self._exercise_payload = (
            exercise.content if isinstance(exercise.content, dict) else {}
        )
        self._exercise_solution = self._exercise_payload.get("solution") or {}

        return {
            "kind": "bac_exercise",
            "id": exercise.id,
            "code": getattr(exercise, "code", ""),
            "title": getattr(exercise, "title", ""),
            "text": clean_text(getattr(exercise, "statement", ""), 8000),
            "year": getattr(exercise, "year", None),
            "exercise_number": getattr(exercise, "exercise_number", None),
            "axis_tags": axis_tags,
            "question_count": len(getattr(exercise, "questions", []) or []),
            "verified": True,
        }

    def _resolve_generated_axis_exercise(self, *, raw_id, axis, kind=None):
        model = self._find_model(
            "GeneratedExercise",
            preferred_labels=("exercise_generation", "generated_exercises"),
        )
        if model is None or not raw_id:
            return None
        pk = self._coerce_model_pk(model, raw_id)
        if pk is None:
            return None

        qs = model.objects.filter(id=pk, is_active=True)

        # Relation de propriété: exercice personnel OU exercice global (student NULL).
        qs = qs.filter(Q(student=self.student) | Q(student__isnull=True))
        qs = qs.filter(axis__chapter=self.chapter)
        if axis is not None:
            qs = qs.filter(axis=axis)

        exercise = qs.select_related("axis").first()
        if exercise is None:
            return None

        self._exercise_record = exercise
        self._exercise_payload = {
            "question": getattr(exercise, "question", ""),
            "hints": getattr(exercise, "hints", []) or [],
            "solution_steps": getattr(exercise, "solution_steps", []) or [],
            "final_answer": getattr(exercise, "final_answer", ""),
        }
        self._exercise_solution = {
            "steps": getattr(exercise, "solution_steps", []) or [],
            "final_answer": getattr(exercise, "final_answer", ""),
        }

        return {
            "kind": "generated_axis_exercise",
            "id": exercise.id,
            "title": getattr(exercise, "title", ""),
            "text": clean_text(getattr(exercise, "question", ""), 8000),
            "difficulty": getattr(exercise, "difficulty", ""),
            "exercise_type": getattr(exercise, "exercise_type", ""),
            "skill": getattr(exercise, "skill", ""),
            "hints": self._clean_string_list(getattr(exercise, "hints", []), 6, 500),
            "common_mistake": clean_text(
                getattr(exercise, "common_mistake", ""), 1200
            ),
            "verified": True,
        }

    def _resolve_generated_bac_exercise(self, *, raw_id, axis, kind=None):
        model = self._find_model(
            "GeneratedBacExercise",
            preferred_labels=("generated_bac", "bac_generation"),
        )
        if model is None or not raw_id:
            return None
        pk = self._coerce_model_pk(model, raw_id)
        if pk is None:
            return None

        exercise = (
            model.objects
            .select_related("chapter", "branch")
            .filter(
                id=pk,
                student=self.student,
                chapter=self.chapter,
            )
            .first()
        )
        if exercise is None:
            return None

        payload = exercise.exercise if isinstance(exercise.exercise, dict) else {}
        solution = exercise.solution if isinstance(exercise.solution, dict) else {}

        self._exercise_record = exercise
        self._exercise_payload = payload
        self._exercise_solution = solution

        return {
            "kind": "generated_bac_exercise",
            "id": exercise.id,
            "title": getattr(exercise, "title", ""),
            "text": clean_text(
                first_non_empty(payload, "statement", "text", "exercise_statement"),
                8000,
            ),
            "branch": getattr(getattr(exercise, "branch", None), "code", ""),
            "status": getattr(exercise, "status", ""),
            "reference_exercise_ids": list(
                getattr(exercise, "reference_exercise_ids", []) or []
            )[:12],
            "question_count": len(payload.get("questions") or []),
            "verified": True,
        }

    def _resolve_adaptive_question(self, *, raw_id, axis, kind=None):
        if not raw_id:
            return None

        model = self._find_model(
            "AdaptiveTestQuestion",
            preferred_labels=("adaptive_assessment",),
        )
        if model is None:
            return None
        pk = self._coerce_model_pk(model, raw_id)
        if pk is None:
            return None

        question = (
            model.objects
            .select_related(
                "test",
                "test__axis",
                "skill",
                "bac_idea",
                "variant",
            )
            .filter(
                id=pk,
                test__student=self.student,
                test__axis__chapter=self.chapter,
            )
            .first()
        )
        if not question:
            return None
        if axis is not None and question.test.axis_id != axis.id:
            return None

        payload = question.question if isinstance(question.question, dict) else {}
        self._exercise_record = question
        self._exercise_payload = payload
        self._exercise_solution = payload.get("solution") or {}

        statement = first_non_empty(payload, "statement", "text", "question", "prompt")

        return {
            "kind": "adaptive_test_question",
            "id": question.id,
            "title": clean_text(payload.get("title"), 255),
            "text": clean_text(statement, 6500),
            "difficulty": question.difficulty,
            "skill": getattr(question.skill, "name", "") if question.skill_id else "",
            "skill_code": getattr(question.skill, "code", "") if question.skill_id else "",
            "bac_idea": getattr(question.bac_idea, "title", "") if question.bac_idea_id else "",
            "variant": getattr(question.variant, "title", "") if question.variant_id else "",
            "verified": True,
        }

    # ------------------------------------------------------------------
    # Question resolution
    # ------------------------------------------------------------------

    def _resolve_question(self, exercise):
        if not exercise:
            return None

        kind = exercise.get("kind")
        raw = self.page_context.get("question")
        raw = raw if isinstance(raw, dict) else {}

        if kind in {"axis_question", "adaptive_test_question"}:
            self._resolved_question_payload = dict(self._exercise_payload or {})
            self._resolved_question_solution = dict(self._exercise_solution or {})
            return {
                "id": exercise.get("id"),
                "number": raw.get("number") or 1,
                "title": exercise.get("title", ""),
                "text": exercise.get("text", ""),
                "skill": exercise.get("skill", ""),
                "verified": bool(exercise.get("verified")),
            }

        if kind == "generated_axis_exercise":
            self._resolved_question_payload = dict(self._exercise_payload or {})
            self._resolved_question_solution = dict(self._exercise_solution or {})
            return {
                "id": raw.get("id") or f"generated-{exercise.get('id')}",
                "number": 1,
                "title": exercise.get("title", ""),
                "text": exercise.get("text", ""),
                "skill": exercise.get("skill", ""),
                "verified": True,
            }

        questions = self._exercise_payload.get("questions")
        if not isinstance(questions, list) or not questions:
            return self._fallback_question(raw)

        target = self._find_question_item(questions, raw)
        if target is None and len(questions) == 1:
            target = (questions[0], 0)
        if target is None:
            return self._fallback_question(raw)

        item, index = target
        self._resolved_question_payload = item
        self._resolved_question_solution = self._question_solution(kind, item, index)

        return {
            "id": self._question_identifier(item, index),
            "number": item.get("number") or item.get("display_order") or index + 1,
            "code": clean_text(item.get("code"), 150),
            "title": clean_text(item.get("title"), 255),
            "text": clean_text(
                first_non_empty(
                    item,
                    "text",
                    "statement",
                    "standalone_text",
                    "question",
                    "prompt",
                ),
                6500,
            ),
            "skill": clean_text(item.get("skill"), 255),
            "verified": True,
        }

    def _fallback_question(self, raw):
        if not raw:
            return None
        text = clean_text(
            first_non_empty(raw, "text", "statement", "standalone_text", "question"),
            6500,
        )
        if not any([raw.get("id"), raw.get("number"), raw.get("title"), text]):
            return None
        return {
            "id": raw.get("id"),
            "number": raw.get("number") or raw.get("display_order") or "",
            "code": clean_text(raw.get("code"), 150),
            "title": clean_text(raw.get("title"), 255),
            "text": text,
            "skill": clean_text(raw.get("skill"), 255),
            "verified": False,
        }

    def _find_question_item(self, questions, raw):
        raw_id = raw.get("id") or raw.get("question_id")
        raw_number = raw.get("number") or raw.get("display_order")

        for index, item in enumerate(questions):
            if not isinstance(item, dict):
                continue
            candidates = {
                str(value)
                for value in (
                    item.get("id"),
                    item.get("question_id"),
                    item.get("code"),
                    item.get("number"),
                    item.get("display_order"),
                    index + 1,
                )
                if value not in (None, "")
            }
            if raw_id not in (None, "") and str(raw_id) in candidates:
                return item, index
            if raw_number not in (None, "") and str(raw_number) in candidates:
                return item, index
        return None

    def _question_identifier(self, item, index):
        return (
            item.get("id")
            or item.get("question_id")
            or item.get("code")
            or item.get("number")
            or item.get("display_order")
            or index + 1
        )

    def _question_solution(self, kind, question_item, index):
        embedded = question_item.get("solution")
        if isinstance(embedded, dict) and embedded:
            return embedded

        if kind != "generated_bac_exercise":
            return {}

        solution_questions = self._exercise_solution.get("questions")
        if not isinstance(solution_questions, list):
            return self._exercise_solution if isinstance(self._exercise_solution, dict) else {}

        qid = self._question_identifier(question_item, index)
        for s_index, solution_item in enumerate(solution_questions):
            if not isinstance(solution_item, dict):
                continue
            candidates = {
                str(value)
                for value in (
                    solution_item.get("question_id"),
                    solution_item.get("id"),
                    solution_item.get("code"),
                    solution_item.get("number"),
                    solution_item.get("display_order"),
                    s_index + 1,
                )
                if value not in (None, "")
            }
            if str(qid) in candidates:
                return solution_item
        return {}

    # ------------------------------------------------------------------
    # Step resolution
    # ------------------------------------------------------------------

    def _resolve_step(self, exercise, question):
        raw = self.page_context.get("step")
        if not isinstance(raw, dict) or not raw:
            return None

        candidate_steps = []
        if isinstance(self._resolved_question_solution, dict):
            candidate_steps = self._normalize_steps(
                self._resolved_question_solution.get("steps")
                or self._resolved_question_solution.get("solution_steps")
            )

        if not candidate_steps and exercise and exercise.get("kind") == "generated_axis_exercise":
            candidate_steps = self._normalize_steps(
                getattr(self._exercise_record, "solution_steps", [])
            )

        if not candidate_steps and isinstance(self._exercise_solution, dict):
            candidate_steps = self._normalize_steps(
                self._exercise_solution.get("steps")
                or self._exercise_solution.get("solution_steps")
            )

        raw_id = raw.get("id") or raw.get("step_number") or raw.get("number")
        matched = self._find_step(candidate_steps, raw_id)

        if matched is not None:
            step, index = matched
            return {
                "id": step.get("id") or step.get("step_id") or step.get("step_number") or index + 1,
                "number": step.get("step_number") or step.get("number") or index + 1,
                "title": clean_text(step.get("title"), 255),
                "type": clean_text(raw.get("type") or step.get("type") or "solution_step", 100),
                "text": clean_text(
                    first_non_empty(
                        step,
                        "explanation",
                        "content",
                        "text",
                        "calculation",
                        "description",
                        "result",
                        "statement",
                    ),
                    4000,
                ),
                "verified": True,
            }

        # Legacy/UI fallback.
        fallback = {
            "id": clean_text(raw_id, 150),
            "number": raw.get("number") or raw.get("step_number") or "",
            "title": clean_text(raw.get("title"), 255),
            "type": clean_text(raw.get("type"), 100),
            "text": clean_text(
                first_non_empty(
                    raw,
                    "text",
                    "content",
                    "statement",
                    "explanation",
                    "calculation",
                ),
                3500,
            ),
            "verified": False,
        }
        return fallback if any(fallback.values()) else None

    def _find_step(self, steps, raw_id):
        if raw_id in (None, ""):
            return None

        raw_str = str(raw_id)
        raw_number = self._last_number(raw_str)

        for index, step in enumerate(steps):
            candidates = [
                step.get("id"),
                step.get("step_id"),
                step.get("step_number"),
                step.get("number"),
                step.get("order"),
                index + 1,
            ]
            if any(str(value) == raw_str for value in candidates if value not in (None, "")):
                return step, index
            if raw_number is not None:
                for value in candidates:
                    if self._safe_int(value, None) == raw_number:
                        return step, index
        return None

    @staticmethod
    def _normalize_steps(value):
        if isinstance(value, list):
            result = []
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    normalized = dict(item)
                else:
                    normalized = {"explanation": str(item)}
                normalized.setdefault("step_number", index + 1)
                result.append(normalized)
            return result

        if isinstance(value, dict):
            result = []
            for index, (key, item) in enumerate(value.items()):
                if isinstance(item, dict):
                    normalized = dict(item)
                else:
                    normalized = {"explanation": str(item)}
                normalized.setdefault("id", key)
                normalized.setdefault("step_number", index + 1)
                result.append(normalized)
            return result
        return []

    # ------------------------------------------------------------------
    # Student learning state / mistakes
    # ------------------------------------------------------------------

    def _learning_state(self, axis):
        skill_model = self._find_model(
            "StudentSkillMastery",
            preferred_labels=("adaptive_assessment",),
        )
        bac_model = self._find_model(
            "StudentBacIdeaMastery",
            preferred_labels=("adaptive_assessment",),
        )

        skill_rows = []
        bac_rows = []

        if skill_model is not None:
            qs = skill_model.objects.filter(student=self.student).select_related("skill")
            if axis:
                qs = qs.filter(skill__axis=axis)
            else:
                qs = qs.filter(skill__axis__chapter=self.chapter)
            skill_rows = list(qs.order_by("mastery_score")[:30])

        if bac_model is not None:
            qs = bac_model.objects.filter(student=self.student).select_related("bac_idea")
            if axis:
                qs = qs.filter(bac_idea__axis=axis)
            else:
                qs = qs.filter(bac_idea__axis__chapter=self.chapter)
            bac_rows = list(qs.order_by("mastery_score")[:30])

        scores = [float(item.mastery_score or 0) for item in skill_rows]
        scores.extend(float(item.mastery_score or 0) for item in bac_rows)

        attempts = sum(int(getattr(item, "attempts_count", 0) or 0) for item in skill_rows)
        attempts += sum(int(getattr(item, "attempts_count", 0) or 0) for item in bac_rows)

        average = round(mean(scores), 1) if scores else None
        level = self._level_label(average, attempts)

        weak_skills = [
            {
                "code": getattr(item.skill, "code", ""),
                "name": getattr(item.skill, "name", ""),
                "mastery_score": round(float(item.mastery_score or 0), 1),
                "weak_idea_codes": list(getattr(item, "weak_idea_codes", []) or [])[:8],
            }
            for item in skill_rows
            if not getattr(item, "is_mastered", False)
        ][:6]

        weak_bac_ideas = [
            {
                "code": getattr(item.bac_idea, "code", ""),
                "title": getattr(item.bac_idea, "title", ""),
                "mastery_score": round(float(item.mastery_score or 0), 1),
                "weak_variant_codes": list(getattr(item, "weak_variant_codes", []) or [])[:8],
                "misconceptions": list(
                    getattr(item, "detected_misconception_codes", []) or []
                )[:8],
            }
            for item in bac_rows
            if not getattr(item, "is_mastered", False)
        ][:6]

        return {
            "level": level,
            "mastery_score": average,
            "attempts_count": attempts,
            "weak_skills": weak_skills,
            "weak_bac_ideas": weak_bac_ideas,
            "has_learning_history": bool(scores or attempts),
        }

    @staticmethod
    def _level_label(score, attempts):
        if score is None or attempts <= 0:
            return "غير محدد بعد"
        if score < 40:
            return "يحتاج تأسيس"
        if score < 65:
            return "قيد البناء"
        if score < 85:
            return "جيد"
        return "متقن"

    def _recent_mistakes(self, axis):
        answer_model = self._find_model(
            "AdaptiveAnswer",
            preferred_labels=("adaptive_assessment",),
        )
        misconception_model = self._find_model(
            "Misconception",
            preferred_labels=("adaptive_assessment",),
        )
        if answer_model is None:
            return []

        qs = (
            answer_model.objects
            .filter(student=self.student, is_correct=False)
            .select_related(
                "test_question",
                "test_question__test",
                "test_question__skill",
                "test_question__bac_idea",
            )
        )

        if axis:
            qs = qs.filter(test_question__test__axis=axis)
        else:
            qs = qs.filter(test_question__test__axis__chapter=self.chapter)

        rows = list(qs.order_by("-created_at")[:5])
        codes = set()
        for row in rows:
            codes.update(row.detected_misconception_codes or [])

        descriptions = {}
        if misconception_model is not None and codes:
            mq = misconception_model.objects.filter(code__in=codes)
            if axis:
                mq = mq.filter(axis=axis)
            else:
                mq = mq.filter(axis__chapter=self.chapter)
            descriptions = {item.code: item.description for item in mq}

        result = []
        for row in rows:
            tq = row.test_question
            payload = tq.question if isinstance(tq.question, dict) else {}
            statement = first_non_empty(payload, "statement", "text", "question", "prompt")
            feedback = parse_json_maybe(row.feedback)
            teacher_message = clean_text(
                first_non_empty(
                    feedback,
                    "teacher_message",
                    "message",
                    "explanation",
                    "text",
                ),
                1200,
            )
            misconception_codes = list(row.detected_misconception_codes or [])[:8]

            result.append({
                "answer_id": row.id,
                "question": clean_text(statement, 2200),
                "score": round(float(row.score or 0) * 100, 1),
                "feedback": teacher_message,
                "skill": getattr(tq.skill, "name", "") if tq.skill_id else "",
                "bac_idea": getattr(tq.bac_idea, "title", "") if tq.bac_idea_id else "",
                "misconceptions": [
                    {
                        "code": code,
                        "description": clean_text(descriptions.get(code), 500),
                    }
                    for code in misconception_codes
                ],
                "created_at": row.created_at.isoformat() if row.created_at else "",
            })

        return result

    def _recent_confusions(self, axis, exercise):
        result = []

        # 1) Réexplication de خطوة درس إن كان النموذج موجودًا.
        if ReExplainStepHistory is not None and axis is not None:
            rows = (
                ReExplainStepHistory.objects
                .filter(student=self.student, axis=axis)
                .order_by("-updated_at")[:3]
            )
            for item in rows:
                result.append({
                    "type": "lesson_step_reexplanation",
                    "step_id": getattr(item, "step_id", ""),
                    "step_title": getattr(item, "step_title", ""),
                    "step_type": getattr(item, "step_type", ""),
                    "student_question": clean_text(
                        getattr(item, "student_question", ""), 1000
                    ),
                })

        # 2) BAC step re-explanations.
        bac_reexp = self._find_model(
            "BacStepReExplanation",
            preferred_labels=("exercise_bac", "bac_exercises"),
        )
        if bac_reexp is not None:
            qs = bac_reexp.objects.filter(
                student=self.student,
                exercise__chapter=self.chapter,
            )
            if exercise and exercise.get("kind") == "bac_exercise":
                qs = qs.filter(exercise_id=exercise.get("id"))
            for item in qs.order_by("-created_at")[:3]:
                result.append({
                    "type": "bac_step_reexplanation",
                    "exercise_id": item.exercise_id,
                    "question_id": getattr(item, "question_id", ""),
                    "step_number": getattr(item, "step_number", None),
                    "step_title": getattr(item, "step_title", ""),
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                })

        # 3) Generated axis exercise alternative solutions.
        alt_model = self._find_model(
            "GeneratedExerciseAlternativeSolution",
            preferred_labels=("exercise_generation", "generated_exercises"),
        )
        if alt_model is not None:
            qs = alt_model.objects.filter(
                student=self.student,
                exercise__axis__chapter=self.chapter,
            )
            if axis is not None:
                qs = qs.filter(exercise__axis=axis)
            if exercise and exercise.get("kind") == "generated_axis_exercise":
                qs = qs.filter(exercise_id=exercise.get("id"))
            for item in qs.order_by("-created_at")[:2]:
                result.append({
                    "type": "generated_axis_alternative_solution",
                    "exercise_id": item.exercise_id,
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                })

        # 4) Generated BAC re-explanations.
        gen_bac_reexp = self._find_model(
            "GeneratedBacQuestionReExplanation",
            preferred_labels=("generated_bac", "bac_generation"),
        )
        if gen_bac_reexp is not None:
            qs = gen_bac_reexp.objects.filter(
                student=self.student,
                generated_exercise__chapter=self.chapter,
            )
            if exercise and exercise.get("kind") == "generated_bac_exercise":
                qs = qs.filter(generated_exercise_id=exercise.get("id"))
            for item in qs.order_by("-created_at")[:3]:
                result.append({
                    "type": "generated_bac_question_reexplanation",
                    "exercise_id": item.generated_exercise_id,
                    "question_id": getattr(item, "question_id", ""),
                    "attempt_number": getattr(item, "attempt_number", 1),
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                })

        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result[:6]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _model_json(instance, field_name):
        value = getattr(instance, field_name, None)
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _normalize_axis_tags(value):
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if isinstance(item, str):
                tag = item.strip()
            elif isinstance(item, dict):
                tag = str(item.get("tag") or item.get("code") or "").strip()
            else:
                tag = ""
            if tag and tag not in result:
                result.append(tag)
        return result

    @staticmethod
    def _clean_string_list(value, max_items=6, max_length=500):
        if not isinstance(value, list):
            return []
        result = []
        for item in value[:max_items]:
            if isinstance(item, dict):
                text = first_non_empty(
                    item,
                    "text",
                    "content",
                    "hint",
                    "explanation",
                    "title",
                )
            else:
                text = item
            text = clean_text(text, max_length)
            if text:
                result.append(text)
        return result

    @staticmethod
    def _safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _last_number(value):
        import re

        matches = re.findall(r"\d+", str(value or ""))
        return int(matches[-1]) if matches else None

    @staticmethod
    def _coerce_model_pk(model, raw_id):
        if raw_id in (None, ""):
            return None
        try:
            return model._meta.pk.to_python(raw_id)
        except Exception:
            # ID قديم/نصي لا يجب أن يحول طلب Chat كاملًا إلى 500.
            return None

    @staticmethod
    def _find_model(model_name, preferred_labels=()):
        for app_label in preferred_labels:
            try:
                model = apps.get_model(app_label, model_name)
            except (LookupError, ValueError):
                model = None
            if model is not None:
                return model

        # Fallback robuste si l'app_label réel diffère dans le projet.
        lowered = model_name.lower()
        for model in apps.get_models():
            if model.__name__.lower() == lowered:
                return model
        return None
