from __future__ import annotations

from typing import Any

from .exceptions import AIResponseError


ALLOWED_VISUAL_TYPES = {"circuit", "diagram", "graph", "table"}
ALLOWED_CONNECTION_STYLES = {"wire", "arrow", "dashed"}


def normalize_visuals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []

    for index, visual in enumerate(value[:8], start=1):
        if not isinstance(visual, dict):
            continue

        visual_type = str(visual.get("type", "")).strip().lower()
        if visual_type not in ALLOWED_VISUAL_TYPES:
            continue

        cleaned: dict[str, Any] = {
            "id": str(visual.get("id") or f"visual_{index}"),
            "type": visual_type,
            "title": str(visual.get("title", "")).strip(),
        }

        if visual_type == "graph":
            cleaned.update({
                "x_label": str(visual.get("x_label", "x")),
                "y_label": str(visual.get("y_label", "y")),
                "x_domain": visual.get("x_domain", []),
                "y_domain": visual.get("y_domain", []),
                "series": visual.get("series", []) if isinstance(visual.get("series"), list) else [],
            })

        elif visual_type == "table":
            cleaned.update({
                "columns": visual.get("columns", []) if isinstance(visual.get("columns"), list) else [],
                "rows": visual.get("rows", []) if isinstance(visual.get("rows"), list) else [],
                "note": str(visual.get("note", "")).strip(),
            })

        else:
            try:
                width = max(320, min(1200, int(visual.get("width", 760))))
            except (TypeError, ValueError):
                width = 760

            try:
                height = max(180, min(800, int(visual.get("height", 360))))
            except (TypeError, ValueError):
                height = 360

            elements: list[dict[str, Any]] = []
            raw_elements = visual.get("elements", [])
            if isinstance(raw_elements, list):
                for e_index, element in enumerate(raw_elements[:40], start=1):
                    if not isinstance(element, dict):
                        continue
                    elements.append({
                        "id": str(element.get("id") or f"e{e_index}"),
                        "kind": str(element.get("kind", "rectangle")).strip().lower(),
                        "label": str(element.get("label", "")).strip(),
                        "x": element.get("x", 50),
                        "y": element.get("y", 50),
                        "width": element.get("width", 90),
                        "height": element.get("height", 50),
                        "orientation": str(element.get("orientation", "horizontal")).strip().lower(),
                        "direction": str(element.get("direction", "")).strip().lower(),
                        "length": element.get("length", 70),
                        "x2": element.get("x2"),
                        "y2": element.get("y2"),
                    })

            connections: list[dict[str, Any]] = []
            raw_connections = visual.get("connections", [])
            if isinstance(raw_connections, list):
                for connection in raw_connections[:60]:
                    if not isinstance(connection, dict):
                        continue
                    style = str(connection.get("style", "wire")).strip().lower()
                    if style not in ALLOWED_CONNECTION_STYLES:
                        style = "wire"
                    connections.append({
                        "from": str(connection.get("from", "")).strip(),
                        "to": str(connection.get("to", "")).strip(),
                        "label": str(connection.get("label", "")).strip(),
                        "style": style,
                    })

            annotations: list[dict[str, Any]] = []
            raw_annotations = visual.get("annotations", [])
            if isinstance(raw_annotations, list):
                for annotation in raw_annotations[:30]:
                    if not isinstance(annotation, dict):
                        continue
                    annotations.append({
                        "text": str(annotation.get("text", "")).strip(),
                        "x": annotation.get("x", 50),
                        "y": annotation.get("y", 30),
                    })

            cleaned.update({
                "width": width,
                "height": height,
                "elements": elements,
                "connections": connections,
                "annotations": annotations,
            })

        result.append(cleaned)

    return result


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
        if not isinstance(questions, list) or not 4 <= len(questions) <= 6:
            raise AIResponseError("عدد الأسئلة يجب أن يكون بين 4 و6.")

        seen_ids: set[str] = set()
        for index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                raise AIResponseError(f"السؤال رقم {index} غير صالح.")

            question_text = str(question.get("text", "")).strip()
            if not question_text:
                raise AIResponseError(f"نص السؤال رقم {index} فارغ.")

            question_id = str(question.get("id", "")).strip()
            if not question_id or question_id in seen_ids:
                question_id = f"q{index}"

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
            solution_question.setdefault("final_answer", "")
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
            requires_visual = any(marker in original_text for marker in self.DRAW_MARKERS)
            has_visual = bool(solution_question["visuals"]) or any(
                bool(step.get("visuals")) for step in steps if isinstance(step, dict)
            )
            if requires_visual and not has_visual:
                raise AIResponseError(
                    f"السؤال {expected_ids[index]} يطلب رسماً لكن الحل لم يرجع visuals."
                )

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
