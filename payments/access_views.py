from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import (
    Response,
)
from rest_framework.views import (
    APIView,
)

from course.models import Chapter

from .access import (
    chapter_requires_payment,
    get_current_student,
    has_chapter_access,
)


class ChapterAccessCheckView(
    APIView
):
    """
    GET /api/payments/access/chapters/<chapter_id>/

    This endpoint is the source of truth for the React route guard.

    It returns 200 for:
      - free
      - owned
      - payment_required
      - inactive

    It returns 404 ONLY when the Chapter row truly does not exist.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        chapter_id,
    ):
        student = (
            get_current_student(
                request
            )
        )

        chapter = (
            Chapter.objects
            .select_related(
                "subject"
            )
            .filter(
                id=chapter_id,
            )
            .first()
        )

        if not chapter:
            return Response(
                {
                    "allowed": False,
                    "requires_payment": False,
                    "reason": "not_found",
                    "detail": (
                        "هذه الوحدة غير موجودة."
                    ),
                    "chapter": None,
                },
                status=404,
            )

        chapter_data = {
            "id": chapter.id,
            "code": (
                chapter.code
                or f"chapter-{chapter.id}"
            ),
            "title": chapter.title,
            "subject_id": (
                chapter.subject_id
            ),
            "is_active": (
                chapter.is_active
            ),
        }

        if chapter.is_active is False:
            return Response(
                {
                    "allowed": False,
                    "requires_payment": False,
                    "reason": "inactive",
                    "detail": (
                        "هذه الوحدة غير مفعّلة حاليًا."
                    ),
                    "chapter": chapter_data,
                },
                status=200,
            )

        requires_payment = (
            chapter_requires_payment(
                chapter
            )
        )

        # FREE CHAPTER
        if not requires_payment:
            return Response(
                {
                    "allowed": True,
                    "requires_payment": False,
                    "reason": "free",
                    "chapter": chapter_data,
                },
                status=200,
            )

        # PAID + OWNED
        if has_chapter_access(
            student,
            chapter,
        ):
            return Response(
                {
                    "allowed": True,
                    "requires_payment": True,
                    "reason": "owned",
                    "chapter": chapter_data,
                },
                status=200,
            )

        # PAID + NOT OWNED
        return Response(
            {
                "allowed": False,
                "requires_payment": True,
                "reason": (
                    "payment_required"
                ),
                "chapter": chapter_data,
            },
            status=200,
        )
