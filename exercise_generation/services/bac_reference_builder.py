from __future__ import annotations

import re
from typing import Any

from course.models import Question

MAX_REFERENCE_QUESTIONS = 3
MAX_STATEMENT_LENGTH = 900


def _text(value: Any, limit: int) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _statement(question: Question) -> str:
    return str(
        getattr(question, "standalone_text", "")
        or getattr(question, "text", "")
        or getattr(question, "original_text", "")
        or ""
    ).strip()


def _style(statement: str) -> dict[str, Any]:
    statement = re.sub(r"\s+", " ", statement).strip()
    commands = [
        command
        for command in (
            "احسب",
            "أثبت",
            "بين",
            "تحقق",
            "استنتج",
            "عين",
            "ادرس",
            "مثل",
            "ارسم",
            "برهن",
            "أوجد",
        )
        if command in statement
    ]

    numbered = re.findall(r"(?:^|\s)(\d{1,2})\s*[\)）.\-]", statement)
    return {
        "commands": commands[:7],
        "parts_count_hint": min(max(len(numbered), 1), 5),
        "has_graph_wording": any(
            word in statement
            for word in (
                "ارسم",
                "مثل بيانيا",
                "مخطط السلم",
                "التمثيل البياني",
            )
        ),
    }


def _reference(question: Question) -> dict[str, Any]:
    statement = _statement(question)
    return {
        "reference_id": question.id,
        "year": getattr(question, "year", None),
        "title": _text(getattr(question, "title", ""), 140),
        "statement": _text(statement, MAX_STATEMENT_LENGTH),
        "skill": _text(getattr(question, "skill", ""), 180),
        "style": _style(statement),
    }


def get_axis_bac_references(*, axis, exclude_ids=None, limit=3):
    """يرجع أسئلة بكالوريا مرتبطة بنفس axis فقط، ولا يبحث في الفصل كله."""
    safe_limit = max(1, min(int(limit or 3), MAX_REFERENCE_QUESTIONS))
    excluded = set(exclude_ids or [])

    queryset = (
        Question.objects.filter(
            axis=axis,
            is_active=True,
            question_type="bac",
        )
        .exclude(id__in=excluded)
        .order_by("-year", "id")
    )

    candidates = [item for item in queryset[:24] if _statement(item)]
    selected: list[Question] = []
    used_skills: set[str] = set()

    for question in candidates:
        skill = str(getattr(question, "skill", "") or "").strip().lower()
        if skill and skill in used_skills:
            continue
        selected.append(question)
        if skill:
            used_skills.add(skill)
        if len(selected) >= safe_limit:
            break

    for question in candidates:
        if len(selected) >= safe_limit:
            break
        if question not in selected:
            selected.append(question)

    return [_reference(item) for item in selected], [item.id for item in selected]
