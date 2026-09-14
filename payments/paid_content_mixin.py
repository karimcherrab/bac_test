"""
Use this helper inside EVERY backend endpoint that returns paid lesson data.
A React route guard is useful UX, but real security must also exist here.
"""

from django.shortcuts import get_object_or_404

from course.models import Chapter

from .access import (
    get_current_student,
    require_chapter_entitlement,
)


def get_authorized_chapter(
    request,
    *,
    chapter_id,
    subject_id=None,
):
    filters = {
        "id": chapter_id,
        "is_active": True,
    }

    if subject_id is not None:
        filters["subject_id"] = (
            subject_id
        )

    chapter = get_object_or_404(
        Chapter.objects.select_related(
            "subject"
        ),
        **filters,
    )

    student = get_current_student(
        request
    )

    require_chapter_entitlement(
        student,
        chapter,
    )

    return chapter


def require_axis_entitlement(
    request,
    axis,
):
    """
    Call this after loading an Axis in /axes/<id>/
    and /axes/<id>/questions/ endpoints.
    """

    student = get_current_student(
        request
    )

    require_chapter_entitlement(
        student,
        axis.chapter,
    )

    return axis


def require_question_entitlement(
    request,
    question,
):
    """
    Question -> Axis -> Chapter access check.
    """

    student = get_current_student(
        request
    )

    require_chapter_entitlement(
        student,
        question.axis.chapter,
    )

    return question
