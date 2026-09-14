from django.db import transaction
from django.utils import timezone


@transaction.atomic
def finalize_test(test):
    """
    Compatibility helper for older callers.

    In sequential mode, completion is based on blueprint targets, NOT on the
    number of generated question attempts. A wrong answer can create several
    attempts for the same target, so question-count completion would be wrong.
    """
    blueprint = dict(test.blueprint or {})
    slots = list(blueprint.get("slots") or [])
    runtime = dict(blueprint.get("runtime") or {})
    cursor = min(int(runtime.get("cursor_index") or 0), len(slots))

    if not slots:
        score = 100.0
        completed = True
    else:
        score = round((cursor / len(slots)) * 100.0, 2)
        completed = cursor >= len(slots)

    test.score = score
    test.mastery_score = score
    if completed:
        test.status = "completed"
        if not test.completed_at:
            test.completed_at = timezone.now()
    elif test.status not in {"draft", "failed"}:
        test.status = "in_progress"

    test.save()
    return test
