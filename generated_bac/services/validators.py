from __future__ import annotations

from typing import Any

from .exceptions import AIResponseError


from .math_visuals import render_visuals as normalize_visuals
import re

class ExerciseValidator:
    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise AIResponseError("التمرين المولد ليس كائن JSON.")

        title = str(data.get("title", "")).strip()
        statement = str(data.get("statement", "")).strip()
        if not title:
            raise AIResponseError("عنوان التمرين فارغ.")
        if not statement:
            raise AIResponseError("نص التمرين فارغ.")

        questions = data.get("questions", [])
        if not isinstance(questions, list) or not 1 <= len(questions) <= 30:
            raise AIResponseError("عدد الأسئلة غير صالح.")

        seen_ids: set[str] = set()
        for index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                raise AIResponseError(f"السؤال رقم {index} غير صالح.")

            question_text = str(question.get("text", "")).strip()
            if not question_text:
                raise AIResponseError(f"نص السؤال رقم {index} فارغ.")

            question_id = str(question.get("id", "")).strip()
            if not question_id:
                question_id = f"q{index}"
            if question_id in seen_ids:
                raise AIResponseError("معرفات الأسئلة مكررة.")

            seen_ids.add(question_id)
            question["id"] = question_id
            question["display_order"] = index
            question.setdefault("skill", "")
            question.setdefault("points", 1)
            question["visuals"] = normalize_visuals(question.get("visuals"))

            for key in (
                "axis_tags", "tag", "tags",
                "solution", "answer", "final_answer", "graph_data",
            ):
                question.pop(key, None)

        for key in (
            "axis_tags", "tag", "tags",
            "solution", "answers", "final_answer", "graph_data",
        ):
            data.pop(key, None)

        data["title"] = title
        data["statement"] = statement
        data.setdefault("statement_sections", [])
        data["visuals"] = normalize_visuals(data.get("visuals"))
        data.setdefault("estimated_points", 5)
        return data


class SolutionValidator:
    DRAW_MARKERS = (
        "ارسم", "رسم", "مثّل", "مثل", "مخطط", "دارة",
        "منحنى", "راسم الاهتزاز", "القوى", "الشكل التخطيطي",
    )

    def validate(
        self,
        data: dict[str, Any],
        *,
        exercise_id: int,
        exercise: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise AIResponseError("الحل المولد غير صالح.")

        exercise_questions = exercise.get("questions", [])
        expected_ids = [str(q.get("id", "")).strip() for q in exercise_questions]
        solution_questions = data.get("questions", [])

        if not isinstance(solution_questions, list):
            raise AIResponseError("questions داخل الحل يجب أن تكون قائمة.")
        if len(solution_questions) != len(expected_ids):
            raise AIResponseError("الحل لا يحتوي إجابة لكل سؤال.")

        if any(not isinstance(q, dict) for q in solution_questions):
            raise AIResponseError("أحد أجوبة الحل ليس كائنًا صالحًا.")

        received_ids = [str(q.get("question_id", "")).strip() for q in solution_questions]
        if expected_ids != received_ids:
            raise AIResponseError("ترتيب question_id في الحل لا يطابق التمرين.")

        data["exercise_id"] = exercise_id
        data.setdefault("general_strategy", "")

        for index, solution_question in enumerate(solution_questions):
            original_question = exercise_questions[index]
            original_text = str(original_question.get("text", ""))
            solution_question["question_text"] = original_text
            solution_question.setdefault("strategy", "")
            if not isinstance(solution_question.get("final_answer"), str) or not solution_question["final_answer"].strip():
                raise AIResponseError("الجواب النهائي يجب أن يكون نصًا غير فارغ.")
            solution_question.setdefault("verification", "")
            solution_question.setdefault("hints", [])
            solution_question.setdefault("common_mistakes", [])
            solution_question.setdefault("bac_writing", [])
            solution_question["visuals"] = normalize_visuals(solution_question.get("visuals"))

            steps = solution_question.get("steps", [])
            if not isinstance(steps, list) or not steps:
                raise AIResponseError(f"حل السؤال {expected_ids[index]} لا يحتوي خطوات.")

            for step_index, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    raise AIResponseError("إحدى خطوات الحل غير صالحة.")
                step["step_number"] = step_index
                step.setdefault("title", "")
                step.setdefault("explanation", "")
                step.setdefault("latex", "")
                step["visuals"] = normalize_visuals(step.get("visuals"))
                step.pop("graph_data", None)

            # إذا كان السؤال يطلب رسماً، نتحقق أن النموذج أرجع رسماً
            # إما على مستوى السؤال أو إحدى خطواته.
            requires_visual = bool(re.search(r"ارسم|أرسم|أنشئ.*(?:منحنى|جدول|شكل)|(?:جدول|جدولا|جدولًا)\s*(?:ال)?تغي|مث[ّ]?ل\s*(?:بياني|المنحنى|النقط)", original_text))
            has_visual = bool(solution_question["visuals"]) or any(
                bool(step.get("visuals")) for step in steps if isinstance(step, dict)
            )
            if requires_visual and not has_visual:
                raise AIResponseError(
                    f"السؤال {expected_ids[index]} يطلب رسماً لكن الحل لم يرجع visuals."
                )

            from .physics_policy import question_requirements
            if exercise.get("subject_code") == "physics":
                needed = set(question_requirements(original_question))
                actual = {v.get("type") for v in solution_question["visuals"]}
                for step in steps:
                    actual.update(v.get("type") for v in step["visuals"])
                if needed - actual:
                    raise AIResponseError("أكمل الرسم المطلوب في حل السؤال " + expected_ids[index] + ": " + ", ".join(sorted(needed-actual)))

            solution_question.pop("graph_data", None)

        data.pop("graph_data", None)
        data.setdefault(
            "final_verification",
            {
                "all_questions_answered": True,
                "mathematical_consistency": "",
                "dependency_consistency": "",
            },
        )
        return data




class QuestionSolutionReExplanationValidator:
    def validate(
        self,
        data: dict[str, Any],
        *,
        question_id: str,
    ) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise AIResponseError("إعادة شرح الحل غير صالحة.")

        cleaned: dict[str, Any] = {
            "question_id": str(question_id),
            "title": str(
                data.get(
                    "title",
                    "شرح مبسط للحل",
                )
            ).strip() or "شرح مبسط للحل",
            "simple_idea": str(
                data.get("simple_idea", "")
            ).strip(),
            "final_answer": str(
                data.get("final_answer", "")
            ).strip(),
            "visuals": normalize_visuals(
                data.get("visuals")
            ),
        }

        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list):
            raw_steps = []

        steps: list[dict[str, Any]] = []

        for index, step in enumerate(
            raw_steps[:7],
            start=1,
        ):
            if not isinstance(step, dict):
                continue

            explanation = str(
                step.get("explanation", "")
            ).strip()

            latex = str(
                step.get("latex", "")
            ).strip()

            title = str(
                step.get("title", "")
            ).strip()

            if not explanation and not latex:
                continue

            steps.append(
                {
                    "step_number": index,
                    "title": title,
                    "explanation": explanation,
                    "latex": latex,
                    "visuals": normalize_visuals(
                        step.get("visuals")
                    ),
                }
            )

        if not cleaned["simple_idea"] and not steps:
            raise AIResponseError(
                "النموذج لم يرجع إعادة شرح مفيدة للحل."
            )

        cleaned["steps"] = steps
        return cleaned
