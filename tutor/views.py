from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import (
    Chapter,
    Axis,
)

from tutor.models import TutorChatSession
from tutor.serializers import (
    TutorChatRequestSerializer,
    TutorChatSessionSerializer,
    TutorChatSessionDetailSerializer,
)
from tutor.services.chat.tutor_chat_service import (
    TutorChatService,
)


class TutorChatAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        serializer = TutorChatRequestSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        student = request.user

        session_id = data.get(
            "session_id"
        )

        # -----------------------------------
        # Session existante
        # -----------------------------------

        if session_id:

            session = get_object_or_404(
                TutorChatSession.objects.select_related(
                    "chapter",
                    "axis",
                ),
                id=session_id,
                student=student,
                is_active=True,
            )

        # -----------------------------------
        # Nouvelle session
        # -----------------------------------

        else:

            chapter = None
            axis = None

            chapter_id = data.get(
                "chapter_id"
            )

            axis_id = data.get(
                "axis_id"
            )

            if chapter_id:
                chapter = get_object_or_404(
                    Chapter,
                    id=chapter_id,
                )

            if axis_id:
                axis = get_object_or_404(
                    Axis.objects.select_related(
                        "chapter"
                    ),
                    id=axis_id,
                    is_active=True,
                )

                # Axis يحدد Chapter تلقائيًا
                chapter = axis.chapter

            session = TutorChatSession.objects.create(
                student=student,
                chapter=chapter,
                axis=axis,
            )

        result = TutorChatService().answer(
            student=student,
            question=data["question"],
            session=session,
        )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )


class TutorChatSessionListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        sessions = (
            TutorChatSession.objects
            .filter(
                student=request.user,
                is_active=True,
            )
            .select_related(
                "chapter",
                "axis",
            )
            .order_by("-updated_at")
        )

        serializer = TutorChatSessionSerializer(
            sessions,
            many=True,
        )

        return Response(
            serializer.data
        )


class TutorChatSessionDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        session_id,
    ):

        session = get_object_or_404(
            TutorChatSession.objects
            .prefetch_related(
                "messages"
            ),
            id=session_id,
            student=request.user,
        )

        serializer = (
            TutorChatSessionDetailSerializer(
                session
            )
        )

        return Response(
            serializer.data
        )