import logging

from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from ..models import Question

from .simple_solution_service import SimpleQuestionSolutionService, SimpleQuestionSolutionParsingError, \
    SimpleQuestionSolutionError
from ..serializers import QuestionSimpleSolutionRequestSerializer, QuestionSimpleSolutionResponseSerializer

from ..views import BaseStudentAPIView

logger = logging.getLogger(__name__)


class QuestionSimpleSolutionAPIView(BaseStudentAPIView):
    """
    POST /api/course/questions/<question_id>/simple-solution/

    React يرسل فقط body اختياري مثل:
    {"regenerate": true}

    الخادم يجلب السؤال والحل والرسم والمادة من قاعدة البيانات.
    """

    serializer_class = QuestionSimpleSolutionRequestSerializer

    @extend_schema(
        request=QuestionSimpleSolutionRequestSerializer,
        responses={200: QuestionSimpleSolutionResponseSerializer},
    )
    def post(self, request, question_id):
        serializer = self.get_serializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        question = get_object_or_404(
            Question.objects.select_related(
                "axis",
                "axis__chapter",
                "axis__chapter__subject",
                "branch",
            ),
            id=question_id,
            is_active=True,
            axis__is_active=True,
            axis__chapter__is_active=True,
        )

        try:
            generated = SimpleQuestionSolutionService().generate(
                question=question,
            )

            response_data = {
                "success": True,
                "question_id": question.id,
                "subject": question.axis.chapter.subject.name,
                "model": generated.model_name,
                "simple_solution": generated.solution,
            }

            output = QuestionSimpleSolutionResponseSerializer(
                data=response_data,
            )
            output.is_valid(raise_exception=True)

            return Response(
                output.data,
                status=status.HTTP_200_OK,
            )

        except SimpleQuestionSolutionParsingError as exc:
            logger.warning(
                "Simple solution parsing failed question=%s student=%s: %s",
                question.id,
                request.user.pk,
                exc,
            )
            return Response(
                {
                    "success": False,
                    "detail": "تم إنشاء جواب غير مكتمل. أعد المحاولة.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        except SimpleQuestionSolutionError as exc:
            logger.exception(
                "Simple solution generation failed question=%s student=%s",
                question.id,
                request.user.pk,
            )
            return Response(
                {
                    "success": False,
                    "detail": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        except Exception:
            logger.exception(
                "Unexpected simple solution error question=%s student=%s",
                question.id,
                request.user.pk,
            )
            return Response(
                {
                    "success": False,
                    "detail": "حدث خطأ أثناء إنشاء الحل المبسط. أعد المحاولة.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
