from django.db.models import Q

from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
)

from accounts.models import Student

from .models import (
    Pack,
    StudentAccess,
)


def try_get_student(request):
    user = getattr(
        request,
        "user",
        None,
    )

    if (
        not user
        or not getattr(
            user,
            "is_authenticated",
            False,
        )
    ):
        return None

    # Your authentication can put Student directly in request.user.
    if isinstance(
        user,
        Student,
    ):
        return user

    # Compatibility if request.user is another User model with
    # a related Student profile.
    for attribute in (
        "student",
        "student_profile",
    ):
        try:
            student = getattr(
                user,
                attribute,
                None,
            )
        except Exception:
            student = None

        if isinstance(
            student,
            Student,
        ):
            return student

    return None


def get_current_student(request):
    student = try_get_student(
        request
    )

    if not student:
        raise NotAuthenticated(
            "Student account not found."
        )

    return student


def has_subject_access(
    student,
    subject,
):
    if (
        not student
        or not subject
    ):
        return False

    return (
        StudentAccess.objects
        .filter(
            student=student,
            subject=subject,
        )
        .exists()
    )


def has_chapter_access(
    student,
    chapter,
):
    """
    A chapter is owned when:
      1) student bought this exact chapter
      OR
      2) student bought the whole subject.
    """

    if (
        not student
        or not chapter
    ):
        return False

    return (
        StudentAccess.objects
        .filter(
            student=student,
        )
        .filter(
            Q(
                chapter_id=chapter.id
            )
            |
            Q(
                subject_id=(
                    chapter.subject_id
                )
            )
        )
        .exists()
    )


def chapter_requires_payment(
    chapter,
):
    """
    SAME RULE AS CoursePage:

    - An active chapter Pack exists -> paid chapter.
    - No active chapter Pack -> free chapter.

    A subject Pack by itself does NOT turn every chapter into a
    paid chapter, because your React page currently treats chapters
    without a chapter Pack as free.
    """

    if not chapter:
        return False

    return (
        Pack.objects
        .filter(
            pack_type=(
                Pack.PackType.CHAPTER
            ),
            chapter_id=chapter.id,
            is_active=True,
        )
        .exists()
    )


def has_chapter_entitlement(
    student,
    chapter,
):
    if not chapter:
        return False

    if not chapter_requires_payment(
        chapter
    ):
        return True

    return has_chapter_access(
        student,
        chapter,
    )


def has_pack_access(
    student,
    pack,
):
    if (
        pack.pack_type
        == Pack.PackType.SUBJECT
    ):
        return has_subject_access(
            student,
            pack.subject,
        )

    return has_chapter_access(
        student,
        pack.chapter,
    )


def require_chapter_entitlement(
    student,
    chapter,
):
    if not has_chapter_entitlement(
        student,
        chapter,
    ):
        raise PermissionDenied(
            "يجب شراء هذه الوحدة أو المادة كاملة للوصول إلى المحتوى."
        )

    return True


def require_subject_access(
    student,
    subject,
):
    if not has_subject_access(
        student,
        subject,
    ):
        raise PermissionDenied(
            "يجب شراء هذه المادة للوصول إليها."
        )
