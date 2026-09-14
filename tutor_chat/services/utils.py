import json


def clean_text(value, limit=3000):
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return text[:limit]


def compact_json(value, limit=7000):
    if value in (None, "", [], {}):
        return ""

    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)

    return text[:limit]


def parse_json_maybe(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"text": str(value)}


def first_non_empty(mapping, *keys):
    if not isinstance(mapping, dict):
        return ""
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return ""
