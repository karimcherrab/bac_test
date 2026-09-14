from __future__ import annotations

import json
import re
from typing import Any, Iterable

from course.models import Question

try:
    from exercise_bac.models import ExerciseBac
except ImportError:  # l'application peut être absente dans certains déploiements
    ExerciseBac = None

MAX_REFERENCE_QUESTIONS = 4
MAX_STATEMENT_LENGTH = 1400
MAX_DOCUMENTS_PER_REFERENCE = 4


def _text(value: Any, limit: int = 500) -> str:
    value = str(value or "").strip()
    return value if len(value) <= limit else value[:limit].rstrip() + "..."


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _statement(question: Question) -> str:
    return str(getattr(question, "standalone_text", "") or getattr(question, "text", "") or getattr(question, "original_text", "") or "").strip()


def _style(statement: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", " ", statement).strip()
    commands = [x for x in ("حلل", "فسر", "استنتج", "اقترح", "قارن", "علل", "بين", "تعرف", "سم", "صف", "مثل", "احسب", "لخص") if x in compact]
    numbered = re.findall(r"(?:^|\s)(\d{1,2})\s*[\)）.\-]", compact)
    return {
        "commands": commands[:8],
        "parts_count_hint": min(max(len(numbered), 1), 6),
        "has_document_wording": any(w in compact for w in ("الوثيقة", "الشكل", "الجدول", "المنحنى")),
        "has_scientific_text": "نص علمي" in compact,
    }


def _candidate_payloads(question: Question) -> Iterable[dict[str, Any]]:
    objects = [question]
    for name in ("exercise", "exercise_bac", "bac_exercise", "source_exercise"):
        parent = getattr(question, name, None)
        if parent is not None:
            objects.append(parent)
    seen: set[int] = set()
    for obj in objects:
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        for attr in ("content", "data", "payload", "metadata", "raw_content", "raw_ai_response"):
            payload = _dict(getattr(obj, attr, None))
            if payload:
                yield payload


def _iter_figures(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_figures(item)
        return
    if not isinstance(payload, dict):
        return
    for key in ("figures", "documents", "document_bank"):
        if isinstance(payload.get(key), list):
            for item in payload[key]:
                if isinstance(item, dict):
                    yield item
    for key in ("exercise", "source", "content", "normalized_exercise"):
        if isinstance(payload.get(key), (dict, list)):
            yield from _iter_figures(payload[key])


def _statement_document(figure: dict[str, Any]) -> dict[str, Any] | None:
    path = _text(figure.get("path") or figure.get("image_path") or figure.get("src"), 500)
    if not path:
        return None
    usage = _text(figure.get("usage") or "statement", 30).lower()
    metadata = _dict(figure.get("metadata"))
    policy = _dict(metadata.get("usage_policy"))
    if usage in {"solution", "answer", "correction"} or policy.get("can_appear_in_generated_statement") is False or _text(policy.get("generator_eligibility"), 80).lower() == "solution_reference_only":
        return None
    def take_list(key: str, limit: int) -> list[Any]:
        value = metadata.get(key, [])
        return value[:limit] if isinstance(value, list) else []
    return {
        "id": _text(figure.get("id") or metadata.get("document_key") or path, 180),
        "title": _text(figure.get("title") or metadata.get("visual_summary") or "وثيقة علمية", 220),
        "path": path,
        "document_type": _text(metadata.get("document_type") or figure.get("type") or "image", 80),
        "scientific_focus": take_list("scientific_focus", 8),
        "visual_summary": _text(metadata.get("visual_summary"), 700),
        "observable_elements": take_list("observable_elements", 12),
        "scientific_relationship": _text(metadata.get("scientific_relationship"), 700),
        "question_operations": take_list("question_operations", 8),
        "answer_invariants": take_list("answer_invariants", 12),
        "forbidden_changes": take_list("forbidden_changes", 12),
        "reuse_mode": _text(_dict(metadata.get("ai_generation_contract")).get("reuse_mode") or "reuse_unchanged_image", 80),
    }


def _documents(question: Question) -> list[dict[str, Any]]:
    result, used_paths = [], set()
    for payload in _candidate_payloads(question):
        for figure in _iter_figures(payload):
            document = _statement_document(figure)
            if not document or document["path"] in used_paths:
                continue
            used_paths.add(document["path"])
            result.append(document)
            if len(result) >= MAX_DOCUMENTS_PER_REFERENCE:
                return result
    return result


def _documents_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result, used_paths = [], set()
    for figure in _iter_figures(payload):
        document = _statement_document(figure)
        if not document or document["path"] in used_paths:
            continue
        used_paths.add(document["path"])
        result.append(document)
    return result


def _axis_bank_documents(axis) -> list[dict[str, Any]]:
    """Fallback direct vers ExerciseBac.content, où sont stockées figures + metadata."""
    if ExerciseBac is None:
        return []
    field_names = {field.name for field in ExerciseBac._meta.get_fields()}
    filters: dict[str, Any] = {}
    chapter = getattr(axis, "chapter", None)
    if chapter is not None and "chapter" in field_names:
        filters["chapter"] = chapter
    if "is_active" in field_names:
        filters["is_active"] = True
    queryset = ExerciseBac.objects.filter(**filters).order_by("-year", "id")[:40]
    axis_tag = _text(getattr(axis, "tag", ""), 200).lower()
    result, used_paths = [], set()
    for exercise in queryset:
        payload = _dict(getattr(exercise, "content", None))
        tags = payload.get("axis_tags", getattr(exercise, "axis_tags", []))
        normalized_tags = {_text(tag, 200).lower() for tag in tags} if isinstance(tags, list) else set()
        if axis_tag and normalized_tags and axis_tag not in normalized_tags:
            continue
        for document in _documents_from_payload(payload):
            if document["path"] in used_paths:
                continue
            used_paths.add(document["path"])
            result.append({**document, "exercise_bac_id": exercise.id})
    return result[:12]


def _axis_bank_references(axis) -> list[dict[str, Any]]:
    """Construit des références synthétiques quand aucun Question bac n'existe."""
    if ExerciseBac is None:
        return []
    field_names = {field.name for field in ExerciseBac._meta.get_fields()}
    filters: dict[str, Any] = {}
    chapter = getattr(axis, "chapter", None)
    if chapter is not None and "chapter" in field_names:
        filters["chapter"] = chapter
    if "is_active" in field_names:
        filters["is_active"] = True
    axis_tag = _text(getattr(axis, "tag", ""), 200).lower()
    result = []
    for exercise in ExerciseBac.objects.filter(**filters).order_by("-year", "id")[:40]:
        payload = _dict(getattr(exercise, "content", None))
        tags = payload.get("axis_tags", getattr(exercise, "axis_tags", []))
        normalized_tags = {_text(tag, 200).lower() for tag in tags} if isinstance(tags, list) else set()
        if axis_tag and normalized_tags and axis_tag not in normalized_tags:
            continue
        statement = _text(payload.get("statement") or getattr(exercise, "question", ""), MAX_STATEMENT_LENGTH)
        documents = _documents_from_payload(payload)
        if not statement or not documents:
            continue
        result.append({
            "reference_id": -int(exercise.id),
            "source_kind": "exercise_bac",
            "year": getattr(exercise, "year", payload.get("year")),
            "title": _text(getattr(exercise, "title", "") or payload.get("title"), 180),
            "statement": statement,
            "skill": "",
            "style": _style(statement),
            "documents": documents,
        })
    return result


def _reference(question: Question) -> dict[str, Any]:
    statement = _statement(question)
    return {
        "reference_id": question.id,
        "year": getattr(question, "year", None),
        "title": _text(getattr(question, "title", ""), 180),
        "statement": _text(statement, MAX_STATEMENT_LENGTH),
        "skill": _text(getattr(question, "skill", ""), 240),
        "style": _style(statement),
        "documents": _documents(question),
    }


def get_axis_bac_references(*, axis, exclude_ids=None, limit=3):
    safe_limit = max(1, min(int(limit or 3), MAX_REFERENCE_QUESTIONS))
    queryset = Question.objects.filter(axis=axis, is_active=True, question_type="bac").exclude(id__in=set(exclude_ids or [])).order_by("-year", "id")
    references = [_reference(item) for item in queryset[:32] if _statement(item)]
    subject = getattr(getattr(axis, "chapter", None), "subject", None)
    source = f"{getattr(subject, 'code', '')} {getattr(subject, 'name', '')}".lower()
    is_science = any(x in source for x in ("science", "sciences", "svt", "طبيعة", "علوم"))
    if is_science and not references:
        references = _axis_bank_references(axis)
    if is_science:
        references.sort(key=lambda x: (not bool(x["documents"]), -(x.get("year") or 0)))
        bank_documents = _axis_bank_documents(axis)
        if bank_documents and references:
            existing = {doc["path"] for ref in references for doc in ref.get("documents", [])}
            references[0]["documents"].extend(
                doc for doc in bank_documents if doc["path"] not in existing
            )
    selected, used_skills = [], set()
    for reference in references:
        skill = _text(reference.get("skill"), 240).lower()
        if skill and skill in used_skills:
            continue
        selected.append(reference)
        if skill:
            used_skills.add(skill)
        if len(selected) >= safe_limit:
            break
    for reference in references:
        if len(selected) >= safe_limit:
            break
        if reference not in selected:
            selected.append(reference)
    return selected, [int(x["reference_id"]) for x in selected]


def collect_allowed_documents(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result, used_paths = [], set()
    for reference in references or []:
        for document in reference.get("documents", []) if isinstance(reference, dict) else []:
            if not isinstance(document, dict):
                continue
            path = _text(document.get("path"), 500)
            if path and path not in used_paths:
                used_paths.add(path)
                result.append({**document, "reference_id": reference.get("reference_id")})
                if len(result) >= 6:
                    return result
    return result
