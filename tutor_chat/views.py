import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Chapter

from .models import StudentSession
from .serializers import (
    StudentMessageSerializer,
    StudentSessionSerializer,
    TutorChatRequestSerializer,
)
from .services.llm import AnswerGenerationError
from .services.orchestrator import TutorOrchestrator
from .services.student import get_student

logger = logging.getLogger(__name__)


class TutorChatAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TutorChatRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_student(request.user)
        if student is None:
            return Response(
                {
                    "success": False,
                    "error": "لم يتم العثور على حساب الطالب المرتبط بالمستخدم.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        chapter = data["chapter"]
        question = data["question"]
        page_context = data.get("page_context") or {}
        session = data.get("session")

        try:
            result = TutorOrchestrator().handle(
                question=question,
                student=student,
                chapter=chapter,
                page_context=page_context,
                session=session,
            )
        except AnswerGenerationError as exc:
            logger.exception("Tutor LLM failed")
            return Response(
                {
                    "success": False,
                    "error": "تعذر الحصول على إجابة من المساعد الذكي.",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except DatabaseError as exc:
            logger.exception("Tutor database error: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": "حدث خطأ أثناء حفظ المحادثة.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            logger.exception("Unexpected tutor error: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": "حدث خطأ غير متوقع أثناء معالجة السؤال.",
                    "details": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        context = result.context
        axis = context.get("axis") or {}
        chapter_context = context.get("chapter") or {}
        exercise = context.get("exercise") or {}
        current_question = context.get("question") or {}
        step = context.get("step") or {}
        learning = context.get("student_learning") or {}
        section = context.get("section") or {}

        return Response(
            {
                "success": True,
                "session_id": result.session_id,
                "answer": result.answer,
                "intent": result.intent,
                "mode": result.mode,
                "model": result.model,
                "chapter_id": chapter_context.get("id"),
                "chapter_code": chapter_context.get("code", ""),
                "chapter_title": chapter_context.get("title", ""),
                "axis_id": axis.get("id"),
                "axis_tag": axis.get("tag", ""),
                "axis_title": axis.get("title", ""),
                "section_id": section.get("id", ""),
                "section_title": section.get("title", ""),
                "exercise": {
                    "kind": exercise.get("kind", ""),
                    "id": exercise.get("id"),
                    "title": exercise.get("title", ""),
                    "verified": exercise.get("verified", False),
                } if exercise else None,
                "question": {
                    "id": current_question.get("id"),
                    "number": current_question.get("number"),
                    "title": current_question.get("title", ""),
                    "verified": current_question.get("verified", False),
                } if current_question else None,
                "step": {
                    "id": step.get("id"),
                    "number": step.get("number"),
                    "title": step.get("title", ""),
                    "type": step.get("type", ""),
                    "verified": step.get("verified", False),
                } if step else None,
                "student_level": learning.get("level", "غير محدد بعد"),
                "mastery_score": learning.get("mastery_score"),
                "recent_mistakes_count": len(context.get("recent_mistakes") or []),
                "context_used": {
                    "has_axis": bool(axis),
                    "has_exercise": bool(exercise),
                    "has_question": bool(current_question),
                    "has_step": bool(step),
                    "solution_visible": bool((context.get("view_state") or {}).get("solution_visible")),
                    "has_selection": bool(context.get("selection")),
                    "has_learning_history": bool(learning.get("has_learning_history")),
                },
                "sources": result.sources,
                "suggestions": result.suggestions,
            },
            status=status.HTTP_200_OK,
        )


class CurrentSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chapter_id):
        student = get_student(request.user)
        if student is None:
            return Response(
                {"detail": "لم يتم العثور على حساب الطالب."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chapter = Chapter.objects.filter(id=chapter_id, is_active=True).first()
        if chapter is None:
            return Response(
                {"detail": "الفصل غير موجود."},
                status=status.HTTP_404_NOT_FOUND,
            )

        session = (
            StudentSession.objects
            .select_related("chapter", "current_axis")
            .prefetch_related("messages")
            .filter(
                student=student,
                chapter=chapter,
                is_active=True,
            )
            .order_by("-updated_at")
            .first()
        )

        if session is None:
            return Response({"session": None}, status=status.HTTP_200_OK)

        return Response(
            {"session": StudentSessionSerializer(session).data},
            status=status.HTTP_200_OK,
        )


class SessionMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        student = get_student(request.user)
        if student is None:
            return Response(
                {"detail": "لم يتم العثور على حساب الطالب."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = (
            StudentSession.objects
            .filter(id=session_id, student=student)
            .first()
        )
        if session is None:
            return Response(
                {"detail": "الجلسة غير موجودة."},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = session.messages.order_by("created_at")
        return Response(
            {
                "session_id": str(session.id),
                "title": session.title,
                "messages": StudentMessageSerializer(messages, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class CloseSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        student = get_student(request.user)
        if student is None:
            return Response(
                {"detail": "لم يتم العثور على حساب الطالب."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = StudentSession.objects.filter(
            id=session_id,
            student=student,
        ).update(is_active=False)

        if not updated:
            return Response(
                {"detail": "الجلسة غير موجودة."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"success": True}, status=status.HTTP_200_OK)
