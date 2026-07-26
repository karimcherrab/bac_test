from typing import Any

from .exceptions import AIResponseError


class ExerciseValidator:
    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise AIResponseError("التمرين المولد ليس كائن JSON.")
        if not str(data.get("title", "")).strip():
            raise AIResponseError("عنوان التمرين فارغ.")
        if not str(data.get("statement", "")).strip():
            raise AIResponseError("نص التمرين فارغ.")
        questions = data.get("questions", [])
        if not isinstance(questions, list) or not 4 <= len(questions) <= 6:
            raise AIResponseError("عدد الأسئلة يجب أن يكون بين 4 و6.")
        seen = set()
        for index, question in enumerate(questions, 1):
            if not isinstance(question, dict) or not str(question.get("text", "")).strip():
                raise AIResponseError(f"السؤال رقم {index} غير صالح.")
            question_id = str(question.get("id", "")).strip()
            if not question_id or question_id in seen:
                question_id = f"q{index}"
            seen.add(question_id)
            question["id"] = question_id
            question["display_order"] = index
            question.setdefault("axis_tags", [])
            question.setdefault("skill", "")
            question.setdefault("points", 1)
            for key in ("solution", "answer", "final_answer", "graph_data"):
                question.pop(key, None)
        for key in ("solution", "answers", "graph_data"):
            data.pop(key, None)
        data.setdefault("statement_sections", [])
        data.setdefault("axis_tags", [])
        return data


class SolutionValidator:
    def validate(self, data: dict[str, Any], *, exercise_id: int, exercise: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise AIResponseError("الحل المولد غير صالح.")
        expected = [str(q.get("id", "")) for q in exercise.get("questions", [])]
        questions = data.get("questions", [])
        if not isinstance(questions, list) or len(questions) != len(expected):
            raise AIResponseError("الحل لا يحتوي إجابة لكل سؤال.")
        received = [str(q.get("question_id", "")) for q in questions]
        if expected != received:
            raise AIResponseError("ترتيب حلول الأسئلة لا يطابق التمرين.")
        data["exercise_id"] = exercise_id
        for solution_question in questions:
            steps = solution_question.get("steps", [])
            if not isinstance(steps, list) or not steps:
                raise AIResponseError("أحد الحلول لا يحتوي خطوات.")
            for index, step in enumerate(steps, 1):
                step["step_number"] = index
                step.setdefault("title", "")
                step.setdefault("explanation", "")
                step.setdefault("latex", "")
                step.pop("graph_data", None)
            solution_question.setdefault("hints", [])
            solution_question.setdefault("common_mistakes", [])
            solution_question.setdefault("bac_writing", [])
            solution_question.pop("graph_data", None)
        data.pop("graph_data", None)
        return data
