from django.core.exceptions import ObjectDoesNotExist
from rest_framework.generics import GenericAPIView

from course.models import Chapter, Axis

from .models import     StudentSession
from .serializers import chapterSerializer , axisSerializer  , SessionSerializer , StudentMessageSerializer



# Create your views here.

class chaptersView(GenericAPIView):
    # permission_classes = [IsAdminUser]
    serializer_class = chapterSerializer

    # get all features from admin
    def get(self, request):
        # get the features
        chapters = Chapter.objects.all()
        serializer = chapterSerializer(chapters, many=True)
        return Response({"chapters": serializer.data}, status=status.HTTP_200_OK)



class axisView(GenericAPIView):
    # permission_classes = [IsAdminUser]
    serializer_class = axisSerializer

    # get all features from admin
    def get(self, request):
        # get the features
        axis = Axis.objects.all().order_by("order")
        serializer = axisSerializer(axis, many=True)
        return Response({"axis": serializer.data}, status=status.HTTP_200_OK)


class QuestionBacByAxisView(GenericAPIView):
    serializer_class = axisSerializer

    def get(self, request, axis_id, type_data):
        try:
            axis = Axis.objects.get(id=axis_id)
        except Axis.DoesNotExist:
            return Response(
                {"error": "Axis not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        questions_bac = Axis.objects.filter(
            axis=axis,
            item_type=type_data,
        ).order_by("year", "exercise_title", "question_number")

        serializer = self.get_serializer(questions_bac, many=True)

        return Response(
            {
                "axis": {
                    "id": axis.id,
                    "tag": axis.tag,
                    "title": axis.title,
                },
                "count": questions_bac.count(),
                "questions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

class AxisByChapterView(GenericAPIView):
    serializer_class = axisSerializer

    def get(self, request, chapter_id):
        try:
            chapter = Chapter.objects.get(id=chapter_id)
        except Chapter.DoesNotExist:
            return Response(
                {"error": "Chapter not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        axes = Axis.objects.filter(chapter=chapter).order_by("order")
        serializer = axisSerializer(axes, many=True)

        return Response(
            {
                "chapter": {
                    "id": chapter.id,
                    "code": chapter.code,
                    "title": chapter.title,
                },
                "axes": serializer.data
            },
            status=status.HTTP_200_OK
        )





from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from knowledge.tutor.orchestrator import TutorOrchestrator






from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from .serializers import (
    SolveBacExerciseRequestSerializer,
    SolveBacExerciseResponseSerializer,
)
from knowledge.services.exercise_service_details import SolveBacExerciseService


class SolveBacExerciseAPIView(APIView):

    @extend_schema(
        request=SolveBacExerciseRequestSerializer,
        responses={200: SolveBacExerciseResponseSerializer},
    )
    def post(self, request):
        serializer = SolveBacExerciseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exercise_id = serializer.validated_data["exercise_id"]

        service = SolveBacExerciseService()
        result = service.generate(exercise_id=exercise_id)

        if result is None:
            return Response(
                {"error": "Exercise not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(result, status=status.HTTP_200_OK)



# views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from .serializers import (
    ExplainCourRequestSerializer,
    ExplainCourResponseSerializer,
)
from knowledge.services.explanation_service_cour import ExplainCourService


class ExplainCourAPIView(APIView):

    @extend_schema(
        request=ExplainCourRequestSerializer,
        responses={200: ExplainCourResponseSerializer},
    )
    def post(self, request):
        serializer = ExplainCourRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        axis_id = serializer.validated_data["axis_id"]

        service = ExplainCourService()
        result = service.generate(axis_id=axis_id)

        if result is None:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(result, status=status.HTTP_200_OK)



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from drf_spectacular.utils import extend_schema

from accounts.models import Student
from knowledge.tutor.orchestrator import TutorOrchestrator

from accounts.authentication import StudentJWTAuthentication
from rest_framework.permissions import IsAuthenticated

class TutorAPIView(APIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TutorRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = request.user

        question = serializer.validated_data["question"]
        session_id = serializer.validated_data.get("session_id")
        chapter_code = serializer.validated_data.get("chapter_code", "sequences")

        tutor = TutorOrchestrator()

        result = tutor.handle(
            question=question,
            student=student,
            session_id=str(session_id) if session_id else None,
            chapter_code=chapter_code,
        )

        return Response({
            "session_id": result.session_id,
            "mode": result.mode,
            "answer": result.answer,
            "intent": result.intent,
            "model": result.model,
            "axis_tag": result.axis_tag,
            "axis_title": result.axis_title,
        })
class SessionMessagesAPIView(APIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, session_id):
        student_id = request.user.id

        try:
            session = StudentSession.objects.get(
                id=session_id,
                student_id=student_id,
            )
        except StudentSession.DoesNotExist:
            return Response(
                {"detail": "Session introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = session.messages.all().order_by("created_at")
        serializer = StudentMessageSerializer(messages, many=True)

        return Response(
            {
                "session_id": str(session.id),
                "title": session.title,
                "messages": serializer.data,
            },
            status=status.HTTP_200_OK,
        )




class SessionsView(GenericAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = SessionSerializer

    def get(self, request, current_chapter):
        session = StudentSession.objects.filter(
            student=request.user,
            chapter=current_chapter
        ).first()

        if session is None:
            return Response(
                {"session": None},
                status=status.HTTP_200_OK
            )

        serializer = self.get_serializer(session)

        return Response(
            {"session": serializer.data},
            status=status.HTTP_200_OK
        )









import logging

from django.db import DatabaseError
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
)

from knowledge.retrieval.answer_generator import (
    AnswerGenerationError,
)
from knowledge.chat_serializer import (
    TutorChatErrorSerializer,
    TutorChatRequestSerializer,
    TutorChatResponseSerializer,
)
from knowledge.tutor.orchestrator import TutorOrchestrator


logger = logging.getLogger(__name__)

import logging

from django.db import DatabaseError

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
)

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from knowledge.retrieval.answer_generator import (
    AnswerGenerationError,
)

from knowledge.tutor.orchestrator import TutorOrchestrator


logger = logging.getLogger(__name__)


class TutorChatAPIView(GenericAPIView):
    """
    Assistant IA général avec historique.

    Le chapitre est conservé pour organiser la session,
    mais le modèle ne récupère aucun contenu du cours.

    Il répond depuis ses connaissances générales.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    serializer_class = TutorChatRequestSerializer

    @extend_schema(
        summary="Envoyer une question à l'assistant IA",
        description=(
            "Assistant IA général avec historique de conversation. "
            "Il répond depuis les connaissances générales du modèle. "
            "Il ne récupère pas le contenu des cours."
        ),
        request=TutorChatRequestSerializer,
        responses={
            200: TutorChatResponseSerializer,
            400: TutorChatErrorSerializer,
            401: TutorChatErrorSerializer,
            502: TutorChatErrorSerializer,
            500: TutorChatErrorSerializer,
        },
        examples=[
            OpenApiExample(
                name="Question générale",
                request_only=True,
                value={
                    "chapter_id": 1,
                    "question": (
                        "ما هي عاصمة فرنسا؟"
                    ),
                    "session_id": None,
                },
            ),
            OpenApiExample(
                name="Question de mathématiques",
                request_only=True,
                value={
                    "chapter_id": 1,
                    "question": (
                        "اشرح لي كيف أحسب الحد الرابع "
                        "في متتالية حسابية."
                    ),
                    "session_id": None,
                },
            ),
            OpenApiExample(
                name="Réponse générale",
                response_only=True,
                status_codes=["200"],
                value={
                    "success": True,
                    "session_id": (
                        "3ce4c24a-a3de-4f20-b8c5-153976b117e8"
                    ),
                    "mode": "explanation",
                    "answer": (
                        "عاصمة فرنسا هي باريس."
                    ),
                    "intent": "explanation",
                    "model": "openai/gpt-oss-120b",
                    "chapter_id": 1,
                    "chapter_code": "sequences",
                    "chapter_title": "المتتاليات العددية",
                    "axis_id": None,
                    "axis_tag": "",
                    "axis_title": "",
                    "sources": [],
                },
            ),
        ],
    )
    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        request_serializer = self.get_serializer(
            data=request.data,
        )

        request_serializer.is_valid(
            raise_exception=True,
        )

        data = request_serializer.validated_data

        chapter = data["chapter"]
        question = data["question"]
        session_id = data.get(
            "session_id"
        )

        student = self.get_student(
            request.user
        )

        if student is None:
            return Response(
                {
                    "success": False,
                    "error": (
                        "لم يتم العثور على حساب الطالب "
                        "المرتبط بهذا المستخدم."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            orchestrator = TutorOrchestrator()

            result = orchestrator.handle(
                question=question,
                student=student,
                chapter_id=chapter.id,
                session_id=(
                    str(session_id)
                    if session_id
                    else None
                ),
            )

        except ValueError as exc:
            logger.warning(
                "Tutor validation error: "
                "student=%s chapter=%s error=%s",
                getattr(
                    student,
                    "pk",
                    None,
                ),
                chapter.id,
                exc,
            )

            return Response(
                {
                    "success": False,
                    "error": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except AnswerGenerationError as exc:
            logger.exception(
                "Answer generation failed: "
                "student=%s chapter=%s",
                getattr(
                    student,
                    "pk",
                    None,
                ),
                chapter.id,
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "تعذر الحصول على إجابة من نموذج "
                        "الذكاء الاصطناعي."
                    ),
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        except DatabaseError as exc:
            logger.exception(
                "Database error in TutorChatAPIView: %s",
                exc,
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "حدث خطأ أثناء حفظ المحادثة."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as exc:
            logger.exception(
                "Unexpected TutorChatAPIView error: %s",
                exc,
            )

            return Response(
                {
                    "success": False,
                    "error": (
                        "حدث خطأ غير متوقع أثناء "
                        "معالجة السؤال."
                    ),
                    "details": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response_data = {
            "success": True,

            "session_id": result.session_id,

            "mode": result.mode or "explanation",
            "answer": result.answer,
            "intent": result.intent or "explanation",
            "model": result.model or "",

            "chapter_id": result.chapter_id,
            "chapter_code": (
                result.chapter_code
                or ""
            ),
            "chapter_title": (
                result.chapter_title
                or ""
            ),

            # Aucun axe n'est récupéré.
            "axis_id": None,
            "axis_tag": "",
            "axis_title": "",

            # Aucun contenu de cours n'est utilisé.
            "sources": [],
        }

        response_serializer = (
            TutorChatResponseSerializer(
                data=response_data,
            )
        )

        response_serializer.is_valid(
            raise_exception=True,
        )

        return Response(
            response_serializer.validated_data,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def get_student(user):
        """
        Retourne le Student lié à request.user.

        Cas 1 :
            request.user est directement un Student.

        Cas 2 :
            request.user possède une relation OneToOne
            nommée student.
        """

        if user is None:
            return None

        if not getattr(
            user,
            "is_authenticated",
            False,
        ):
            return None

        if (
            user.__class__.__name__
            == "Student"
        ):
            return user

        try:
            return user.student

        except (
            AttributeError,
            ObjectDoesNotExist,
        ):
            return None