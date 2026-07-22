from __future__ import annotations

from typing import Any

from exercise_generation.services.exceptions import (
    ExerciseValidationError,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_hints(
    value: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    result = []

    for index, item in enumerate(
        value[:3],
        start=1,
    ):
        if isinstance(item, dict):
            hint = _text(item.get("hint"))
            level = item.get("level", index)
        else:
            hint = _text(item)
            level = index

        if not hint:
            continue

        try:
            level = int(level)
        except (TypeError, ValueError):
            level = index

        result.append(
            {
                "level": level,
                "hint": hint,
            }
        )

    return result


def _normalize_steps(
    value: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ExerciseValidationError(
            "solution.steps يجب أن تكون قائمة."
        )

    result = []

    for index, step in enumerate(
        value,
        start=1,
    ):
        if not isinstance(step, dict):
            continue

        title = (
            _text(step.get("title"))
            or f"الخطوة {index}"
        )

        explanation = _text(
            step.get("explanation")
        )

        calculation = _text(
            step.get("calculation")
        )

        step_result = _text(
            step.get("result")
        )

        if not any(
            [
                explanation,
                calculation,
                step_result,
            ]
        ):
            continue

        result.append(
            {
                "order": index,
                "title": title,
                "explanation": explanation,
                "calculation": calculation,
                "result": step_result,
            }
        )

    if not result:
        raise ExerciseValidationError(
            "الحل لا يحتوي على خطوات صالحة."
        )

    return result[:40]


def _normalize_mistakes(
    value: Any,
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    result = []

    for item in value[:3]:
        if isinstance(item, str):
            mistake = _text(item)

            if mistake:
                result.append(
                    {
                        "mistake": mistake,
                        "why_wrong": "",
                        "correction": "",
                    }
                )

            continue

        if not isinstance(item, dict):
            continue

        mistake = _text(
            item.get("mistake")
        )

        why_wrong = _text(
            item.get("why_wrong")
        )

        correction = _text(
            item.get("correction")
        )

        if not any(
            [
                mistake,
                why_wrong,
                correction,
            ]
        ):
            continue

        result.append(
            {
                "mistake": mistake,
                "why_wrong": why_wrong,
                "correction": correction,
            }
        )

    return result


def validate_bac_like_exercise(
    exercise: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(exercise, dict):
        raise ExerciseValidationError(
            "exercise يجب أن يكون JSON object."
        )

    title = _text(
        exercise.get("title")
    )

    question = _text(
        exercise.get("question")
        or exercise.get("standalone_text")
        or exercise.get("text")
    )

    skill = _text(
        exercise.get("skill")
    )

    if not title:
        raise ExerciseValidationError(
            "عنوان التمرين غير موجود."
        )

    if not question:
        raise ExerciseValidationError(
            "نص التمرين غير موجود."
        )

    solution = exercise.get("solution")

    if not isinstance(solution, dict):
        raise ExerciseValidationError(
            "الحل solution غير موجود."
        )

    strategy = _text(
        solution.get("strategy")
    )

    explanation = _text(
        solution.get("detailed_explanation")
    )

    final_answer = _text(
        solution.get("final_answer")
    )

    verification = _text(
        solution.get("verification")
    )

    if not final_answer:
        raise ExerciseValidationError(
            "الجواب النهائي غير موجود."
        )

    steps = _normalize_steps(
        solution.get("steps")
    )

    requires_graph = bool(
        exercise.get("requires_graph", False)
    )

    graph_data = exercise.get(
        "graph_data",
        {},
    )

    if requires_graph and not isinstance(
        graph_data,
        dict,
    ):
        raise ExerciseValidationError(
            "graph_data يجب أن تكون JSON object."
        )

    return {
        "title": title,
        "question": question,
        "skill": skill,
        "hints": _normalize_hints(
            exercise.get("hints")
        ),
        "solution_strategy": strategy,
        "solution_explanation": explanation,
        "solution_steps": steps,
        "final_answer": final_answer,
        "verification": verification,
        "common_mistakes": (
            _normalize_mistakes(
                solution.get("common_mistakes")
            )
        ),
        "alternative_method": _text(
            solution.get("alternative_method")
        ),
        "requires_graph": requires_graph,
        "graph_data": (
            graph_data
            if requires_graph
            else {}
        ),
    }