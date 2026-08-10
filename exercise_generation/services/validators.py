from __future__ import annotations

from typing import Any

from exercise_generation.services.exceptions import ExerciseValidationError


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_hints(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for index, item in enumerate(value[:3], start=1):
        if isinstance(item, dict):
            hint = _text(item.get("hint"))
            level = item.get("level", index)
        else:
            hint, level = _text(item), index
        if not hint:
            continue
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = index
        result.append({"level": level, "hint": hint})
    return result


def _normalize_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ExerciseValidationError("solution.steps يجب أن تكون قائمة.")
    result = []
    for index, step in enumerate(value, start=1):
        if not isinstance(step, dict):
            continue
        item = {
            "order": index,
            "title": _text(step.get("title")) or f"الخطوة {index}",
            "explanation": _text(step.get("explanation")),
            "calculation": _text(step.get("calculation")),
            "result": _text(step.get("result")),
        }
        if any(item[k] for k in ("explanation", "calculation", "result")):
            result.append(item)
    if not result:
        raise ExerciseValidationError("الحل لا يحتوي على خطوات صالحة.")
    return result[:40]


def _normalize_mistakes(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:3]:
        if isinstance(item, str):
            if _text(item):
                result.append({"mistake": _text(item), "why_wrong": "", "correction": ""})
            continue
        if not isinstance(item, dict):
            continue
        normalized = {
            "mistake": _text(item.get("mistake")),
            "why_wrong": _text(item.get("why_wrong")),
            "correction": _text(item.get("correction")),
        }
        if any(normalized.values()):
            result.append(normalized)
    return result


def _normalize_table(item: dict[str, Any]) -> dict[str, Any] | None:
    headers = [_text(v) for v in item.get("headers", [])] if isinstance(item.get("headers"), list) else []
    rows = []
    raw_rows = item.get("rows", [])
    if isinstance(raw_rows, list):
        for row in raw_rows[:20]:
            if isinstance(row, list):
                rows.append([_text(v) for v in row[:12]])
    if not headers or not rows:
        return None
    width = len(headers)
    rows = [(row + [""] * width)[:width] for row in rows]
    return {"type": "table", "title": _text(item.get("title")), "headers": headers[:12], "rows": rows, "caption": _text(item.get("caption"))}


def _normalize_circuit(item: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"resistor", "capacitor", "battery", "generator", "switch", "lamp", "ammeter", "voltmeter", "coil", "node"}
    components = []
    for comp in item.get("components", []) if isinstance(item.get("components"), list) else []:
        if not isinstance(comp, dict):
            continue
        ctype = _text(comp.get("type")).lower()
        cid = _text(comp.get("id"))
        if ctype not in allowed or not cid:
            continue
        components.append({
            "id": cid,
            "type": ctype,
            "label": _text(comp.get("label")),
            "value": _text(comp.get("value")),
            "x": max(0, min(_number(comp.get("x"), 0), 1200)),
            "y": max(0, min(_number(comp.get("y"), 0), 800)),
            "rotation": _number(comp.get("rotation"), 0),
        })
    wires = []
    for wire in item.get("wires", []) if isinstance(item.get("wires"), list) else []:
        if not isinstance(wire, dict):
            continue
        wires.append({
            "x1": max(0, min(_number(wire.get("x1"), 0), 1200)),
            "y1": max(0, min(_number(wire.get("y1"), 0), 800)),
            "x2": max(0, min(_number(wire.get("x2"), 0), 1200)),
            "y2": max(0, min(_number(wire.get("y2"), 0), 800)),
            "label": _text(wire.get("label")),
        })
    if not components:
        return None
    return {
        "type": "circuit",
        "title": _text(item.get("title")),
        "width": max(320, min(int(_number(item.get("width"), 720)), 1200)),
        "height": max(220, min(int(_number(item.get("height"), 360)), 800)),
        "components": components[:24],
        "wires": wires[:40],
        "caption": _text(item.get("caption")),
    }


def _normalize_diagram(item: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"arrow", "line", "point", "circle", "rect", "text"}
    elements = []
    for el in item.get("elements", []) if isinstance(item.get("elements"), list) else []:
        if not isinstance(el, dict):
            continue
        etype = _text(el.get("type")).lower()
        if etype not in allowed:
            continue
        elements.append({
            "type": etype,
            "x1": _number(el.get("x1"), _number(el.get("x"), 0)),
            "y1": _number(el.get("y1"), _number(el.get("y"), 0)),
            "x2": _number(el.get("x2"), 0),
            "y2": _number(el.get("y2"), 0),
            "x": _number(el.get("x"), 0),
            "y": _number(el.get("y"), 0),
            "width": _number(el.get("width"), 80),
            "height": _number(el.get("height"), 50),
            "radius": _number(el.get("radius"), 8),
            "label": _text(el.get("label")),
        })
    if not elements:
        return None
    return {
        "type": "diagram",
        "title": _text(item.get("title")),
        "width": max(320, min(int(_number(item.get("width"), 720)), 1200)),
        "height": max(220, min(int(_number(item.get("height"), 360)), 800)),
        "elements": elements[:40],
        "caption": _text(item.get("caption")),
    }


def _normalize_visuals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        vtype = _text(item.get("type")).lower()
        normalized = None
        if vtype == "table":
            normalized = _normalize_table(item)
        elif vtype == "circuit":
            normalized = _normalize_circuit(item)
        elif vtype == "diagram":
            normalized = _normalize_diagram(item)
        if normalized:
            result.append(normalized)
    return result


def validate_bac_like_exercise(exercise: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(exercise, dict):
        raise ExerciseValidationError("exercise يجب أن يكون JSON object.")
    title = _text(exercise.get("title"))
    question = _text(exercise.get("question") or exercise.get("standalone_text") or exercise.get("text"))
    skill = _text(exercise.get("skill"))
    if not title:
        raise ExerciseValidationError("عنوان التمرين غير موجود.")
    if not question:
        raise ExerciseValidationError("نص التمرين غير موجود.")
    solution = exercise.get("solution")
    if not isinstance(solution, dict):
        raise ExerciseValidationError("الحل solution غير موجود.")
    final_answer = _text(solution.get("final_answer"))
    if not final_answer:
        raise ExerciseValidationError("الجواب النهائي غير موجود.")
    requires_graph = bool(exercise.get("requires_graph", False))
    graph_data = exercise.get("graph_data", {})
    if requires_graph and not isinstance(graph_data, dict):
        raise ExerciseValidationError("graph_data يجب أن تكون JSON object.")
    return {
        "title": title,
        "question": question,
        "skill": skill,
        "hints": _normalize_hints(exercise.get("hints")),
        "visuals": _normalize_visuals(exercise.get("visuals")),
        "solution_strategy": _text(solution.get("strategy")),
        "solution_explanation": _text(solution.get("detailed_explanation")),
        "solution_steps": _normalize_steps(solution.get("steps")),
        "final_answer": final_answer,
        "verification": _text(solution.get("verification")),
        "common_mistakes": _normalize_mistakes(solution.get("common_mistakes")),
        "alternative_method": _text(solution.get("alternative_method")),
        "requires_graph": requires_graph,
        "graph_data": graph_data if requires_graph else {},
    }
