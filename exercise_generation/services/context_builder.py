from typing import Any

MAX_ITEMS = 5


def _text(value: Any, limit: int = 360) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _list(value: Any, limit: int = MAX_ITEMS) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value[:limit]:
        if isinstance(item, dict):
            candidate = (
                item.get("title")
                or item.get("central_idea")
                or item.get("method")
                or item.get("rule")
                or item.get("teacher")
                or item.get("content")
                or item.get("text")
            )
        else:
            candidate = item

        candidate = _text(candidate, 260)
        if candidate:
            result.append(candidate)
    return result


def _learning_path_methods(content: dict[str, Any]) -> list[str]:
    methods: list[str] = []
    path = content.get("learning_path", [])
    if not isinstance(path, list):
        return methods

    for step in path:
        if not isinstance(step, dict):
            continue
        step_content = step.get("content", {})
        if not isinstance(step_content, dict):
            continue

        for key in (
            "central_idea",
            "method",
            "rule",
            "definition",
            "teacher",
            "memory_tip",
        ):
            candidate = _text(step_content.get(key), 300)
            if candidate and candidate not in methods:
                methods.append(candidate)
                break

        if len(methods) >= 5:
            break

    return methods


def build_compact_lesson_context(content: dict[str, Any]) -> dict[str, Any]:
    """يبني سياقًا صغيرًا لكنه كافٍ، ومأخوذ من المحور نفسه فقط."""
    summary = content.get("lesson_summary", {})
    if not isinstance(summary, dict):
        summary = {"text": _text(summary, 600)}

    strategy = content.get("lesson_strategy", {})
    if not isinstance(strategy, dict):
        strategy = {}

    return {
        "title": _text(
            content.get("axis_title") or content.get("title"),
            220,
        ),
        "lesson_goal": _text(content.get("lesson_goal"), 350),
        "learning_outcomes": _list(content.get("learning_outcomes"), 5),
        "main_idea": _text(strategy.get("main_idea"), 320),
        "bac_skill": _text(strategy.get("bac_skill"), 260),
        "common_obstacle": _text(strategy.get("common_obstacle"), 260),
        "key_methods": _learning_path_methods(content),
        "summary": {
            "key_ideas": _list(summary.get("key_ideas"), 5),
            "method_template": _list(summary.get("method_template"), 5),
            "memory_tip": _text(summary.get("memory_tip"), 260),
            "text": _text(summary.get("text"), 500),
        },
    }
