from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from accounts.authentication import StudentJWTAuthentication
from .ReExplicationCour.ReExplainStepService import ReExplainStepService
from .ReExplicationCour.re_explain_step_history_service import ReExplainStepHistoryService
from .ReExplicationCour.serializers import ReExplainStepRequestSerializer, ReExplainStepResponseSerializer, \
    ReExplainStepHistoryListResponseSerializer, ReExplainStepHistorySerializer

from .models import (
    Axis,
    Branch,
    Chapter,
    Question,
    Subject, ReExplainStepHistory,
)

from .serializers import (
    AxisDetailSerializer,
    AxisSummarySerializer,
    BranchDetailSerializer,
    BranchSerializer,
    ChapterDetailSerializer,
    ChapterSummarySerializer,
    QuestionDetailSerializer,
    QuestionSummarySerializer,
    SubjectDetailSerializer,
    SubjectSummarySerializer, SubjectCreateSerializer,
)


class BaseStudentAPIView(GenericAPIView):
    authentication_classes = [
        StudentJWTAuthentication,
    ]

    permission_classes = [
        IsAuthenticated,
    ]


class BranchListView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = BranchSerializer

    def get(self, request):
        branches = Branch.objects.all().order_by(
            "name",
        )

        serializer = self.get_serializer(
            branches,
            many=True,
        )

        return Response(
            {
                "count": branches.count(),
                "branches": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        branch = serializer.save()

        return Response(
            {
                "success": True,
                "branch": BranchSerializer(branch).data,
            },
            status=status.HTTP_201_CREATED,)

class BranchDetailView(BaseStudentAPIView):
    serializer_class = BranchDetailSerializer

    def get(self, request, branch_id):
        branch = get_object_or_404(
            Branch.objects.prefetch_related(
                "subjects",
                "subjects__chapters",
            ),
            id=branch_id,
        )

        serializer = self.get_serializer(
            branch,
        )

        return Response(
            {
                "branch": serializer.data,
            },
            status=status.HTTP_200_OK,
        )



class SubjectListView(BaseStudentAPIView):

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SubjectCreateSerializer
        return SubjectSummarySerializer

    def get(self, request):
        subjects = Subject.objects.prefetch_related(
            "branches",
        )

        branch_id = request.query_params.get(
            "branch_id"
        )

        branch_code = request.query_params.get(
            "branch_code"
        )

        if branch_id:
            subjects = subjects.filter(
                branches__id=branch_id,
            )

        if branch_code:
            subjects = subjects.filter(
                branches__code=branch_code,
            )

        subjects = subjects.distinct().order_by(
            "name",
        )

        serializer = self.get_serializer(
            subjects,
            many=True,
        )

        return Response(
            {
                "count": subjects.count(),
                "subjects": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        subject = serializer.save()

        return Response(
            {
                "success": True,
                "subject": SubjectSummarySerializer(
                    subject
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )
class SubjectDetailView(BaseStudentAPIView):
    serializer_class = SubjectDetailSerializer

    def get(self, request, subject_id):
        subject = get_object_or_404(
            Subject.objects.prefetch_related(
                "branches",
                "chapters",
                "chapters__axes",
            ),
            id=subject_id,
        )

        serializer = self.get_serializer(
            subject,
        )

        return Response(
            {
                "subject": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class SubjectByBranchView(BaseStudentAPIView):
    serializer_class = SubjectSummarySerializer

    def get(self, request):
        student = request.user

        student_branch = getattr(
            student,
            "branch",
            None,
        )

        if student_branch is None:
            return Response(
                {
                    "success": False,
                    "message": (
                        "لم يتم تحديد شعبة الطالب."
                    ),
                    "branch": None,
                    "count": 0,
                    "subjects": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subjects = (
            Subject.objects
            .filter(
                branches=student_branch,
            )
            .prefetch_related(
                "branches",
            )
            .distinct()
            .order_by(
                "name",
            )
        )

        serializer = self.get_serializer(
            subjects,
            many=True,
        )

        return Response(
            {
                "success": True,
                "branch": {
                    "id": student_branch.id,
                    "code": student_branch.code,
                    "name": student_branch.name,
                },
                "count": subjects.count(),
                "subjects": serializer.data,
            },
            status=status.HTTP_200_OK,
        ) 



class ChapterListView(BaseStudentAPIView):
    serializer_class = ChapterSummarySerializer

    def get(self, request):
        chapters = Chapter.objects.select_related(
            "subject",
        ).prefetch_related(
            "axes",
        ).filter(
            is_active=True,
        )

        subject_id = request.query_params.get(
            "subject_id"
        )

        subject_code = request.query_params.get(
            "subject_code"
        )

        branch_id = request.query_params.get(
            "branch_id"
        )

        branch_code = request.query_params.get(
            "branch_code"
        )

        if subject_id:
            chapters = chapters.filter(
                subject_id=subject_id,
            )

        if subject_code:
            chapters = chapters.filter(
                subject__code=subject_code,
            )

        if branch_id:
            chapters = chapters.filter(
                subject__branches__id=branch_id,
            )

        if branch_code:
            chapters = chapters.filter(
                subject__branches__code=branch_code,
            )

        chapters = chapters.distinct().order_by(
            "subject__name",
            "order",
            "title",
        )

        serializer = self.get_serializer(
            chapters,
            many=True,
        )

        return Response(
            {
                "count": chapters.count(),
                "chapters": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ChapterDetailView(BaseStudentAPIView):
    serializer_class = ChapterDetailSerializer

    def get(self, request, chapter_id):
        chapter = get_object_or_404(
            Chapter.objects.select_related(
                "subject",
            ).prefetch_related(
                "axes",
            ),
            id=chapter_id,
            is_active=True,
        )

        serializer = self.get_serializer(
            chapter,
        )

        return Response(
            {
                "chapter": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AxisListView(BaseStudentAPIView):
    serializer_class = AxisSummarySerializer

    def get(self, request):
        axes = Axis.objects.select_related(
            "chapter",
            "chapter__subject",
        ).filter(
            is_active=True,
            chapter__is_active=True,
        )

        chapter_id = request.query_params.get(
            "chapter_id"
        )

        chapter_code = request.query_params.get(
            "chapter_code"
        )

        subject_id = request.query_params.get(
            "subject_id"
        )

        if chapter_id:
            axes = axes.filter(
                chapter_id=chapter_id,
            )

        if chapter_code:
            axes = axes.filter(
                chapter__code=chapter_code,
            )

        if subject_id:
            axes = axes.filter(
                chapter__subject_id=subject_id,
            )

        axes = axes.order_by(
            "chapter__order",
            "order",
            "title",
        )

        serializer = self.get_serializer(
            axes,
            many=True,
        )

        return Response(
            {
                "count": axes.count(),
                "axes": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AxisDetailView(BaseStudentAPIView):
    serializer_class = AxisDetailSerializer

    def get(self, request, axis_id):
        axis = get_object_or_404(
            Axis.objects.select_related(
                "chapter",
                "chapter__subject",
            ),
            id=axis_id,
            is_active=True,
            chapter__is_active=True,
        )

        axis_serializer = self.get_serializer(axis)

        history = (
            ReExplainStepHistory.objects.filter(
                student=request.user,
                axis=axis,
            )
            .order_by("-created_at")
        )

        history_serializer = ReExplainStepHistorySerializer(
            history,
            many=True,
        )

        return Response(
            {
                "axis": axis_serializer.data,
                "re_explain_history": history_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

#
# class AxisQuestionListView(BaseStudentAPIView):
#     """
#     Retourne toutes les questions et leurs solutions
#     pour un axe précis.
#
#     URL :
#     GET /api/course/axes/<axis_id>/questions/
#
#     Filtres optionnels :
#     ?year=2025
#     ?difficulty=medium
#     ?question_type=bac
#     ?has_solution=true
#     """
#
#     serializer_class = QuestionDetailSerializer
#
#     def get(self, request, axis_id):
#         axis = get_object_or_404(
#             Axis.objects.select_related(
#                 "chapter",
#                 "chapter__subject",
#             ),
#             id=axis_id,
#             is_active=True,
#             chapter__is_active=True,
#         )
#
#         questions = Question.objects.select_related(
#             "axis",
#             "axis__chapter",
#             "axis__chapter__subject",
#             "branch",
#             "solution",
#         ).filter(
#             axis=axis,
#             is_active=True,
#         )
#
#         year = request.query_params.get(
#             "year"
#         )
#
#         difficulty = request.query_params.get(
#             "difficulty"
#         )
#
#         question_type = request.query_params.get(
#             "question_type"
#         )
#
#         has_solution = request.query_params.get(
#             "has_solution"
#         )
#
#         if year:
#             try:
#                 questions = questions.filter(
#                     year=int(year),
#                 )
#             except ValueError:
#                 return Response(
#                     {
#                         "detail": (
#                             "Le paramètre year doit être "
#                             "un nombre entier."
#                         )
#                     },
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#
#         if difficulty:
#             allowed_difficulties = {
#                 "easy",
#                 "medium",
#                 "hard",
#             }
#
#             if difficulty not in allowed_difficulties:
#                 return Response(
#                     {
#                         "detail": (
#                             "difficulty doit être easy, "
#                             "medium ou hard."
#                         )
#                     },
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#
#             questions = questions.filter(
#                 difficulty=difficulty,
#             )
#
#         if question_type:
#             allowed_types = {
#                 "bac",
#                 "guided",
#                 "practice",
#                 "quiz",
#             }
#
#             if question_type not in allowed_types:
#                 return Response(
#                     {
#                         "detail": (
#                             "question_type doit être bac, "
#                             "guided, practice ou quiz."
#                         )
#                     },
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#
#             questions = questions.filter(
#                 question_type=question_type,
#             )
#
#         if has_solution is not None:
#             normalized_has_solution = (
#                 has_solution.strip().lower()
#             )
#
#             if normalized_has_solution in {
#                 "true",
#                 "1",
#                 "yes",
#             }:
#                 questions = questions.filter(
#                     solution__isnull=False,
#                 )
#
#             elif normalized_has_solution in {
#                 "false",
#                 "0",
#                 "no",
#             }:
#                 questions = questions.filter(
#                     solution__isnull=True,
#                 )
#
#             else:
#                 return Response(
#                     {
#                         "detail": (
#                             "has_solution doit être "
#                             "true ou false."
#                         )
#                     },
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#
#         questions = questions.order_by(
#             "year",
#             "order",
#             "number",
#             "id",
#         )
#
#         serializer = self.get_serializer(
#             questions,
#             many=True,
#         )
#
#         axis_data = AxisSummarySerializer(
#             axis,
#             context=self.get_serializer_context(),
#         ).data
#
#         return Response(
#             {
#                 "axis": axis_data,
#                 "filters": {
#                     "year": year,
#                     "difficulty": difficulty,
#                     "question_type": question_type,
#                     "has_solution": has_solution,
#                 },
#                 "count": questions.count(),
#                 "questions": serializer.data,
#             },
#             status=status.HTTP_200_OK,
#         )
#
#
# class QuestionDetailView(BaseStudentAPIView):
#     """
#     Retourne une question précise avec sa solution.
#
#     URL :
#     GET /api/course/questions/<question_id>/
#     """
#
#     serializer_class = QuestionDetailSerializer
#
#     def get(self, request, question_id):
#         question = get_object_or_404(
#             Question.objects.select_related(
#                 "axis",
#                 "axis__chapter",
#                 "axis__chapter__subject",
#                 "branch",
#                 "solution",
#             ),
#             id=question_id,
#             is_active=True,
#             axis__is_active=True,
#             axis__chapter__is_active=True,
#         )
#
#         serializer = self.get_serializer(
#             question,
#         )
#
#         return Response(
#             {
#                 "question": serializer.data,
#             },
#             status=status.HTTP_200_OK,
#         )
#
#
# class AxisQuestionSummaryListView(BaseStudentAPIView):
#     """
#     Version légère sans charger le contenu complet
#     de la solution.
#
#     URL :
#     GET /api/course/axes/<axis_id>/questions/summary/
#     """
#
#     serializer_class = QuestionSummarySerializer
#
#     def get(self, request, axis_id):
#         axis = get_object_or_404(
#             Axis,
#             id=axis_id,
#             is_active=True,
#             chapter__is_active=True,
#         )
#
#         questions = Question.objects.select_related(
#             "axis",
#             "branch",
#             "solution",
#         ).filter(
#             axis=axis,
#             is_active=True,
#         ).order_by(
#             "year",
#             "order",
#             "number",
#         )
#
#         serializer = self.get_serializer(
#             questions,
#             many=True,
#         )
#
#         return Response(
#             {
#                 "axis": AxisSummarySerializer(
#                     axis,
#                 ).data,
#                 "count": questions.count(),
#                 "questions": serializer.data,
#             },
#             status=status.HTTP_200_OK,
#         )



from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response

from .models import Axis, Question

from .serializers import (
    AxisSummarySerializer,
    QuestionDetailSerializer,
    QuestionSummarySerializer,
    QuestionWriteSerializer,
)

class AxisQuestionListView(BaseStudentAPIView):
    """
    Retourne toutes les questions d'un axe avec leur solution JSON.

    URL :
    GET /api/course/axes/<axis_id>/questions/

    Filtres :
    ?year=2025
    ?difficulty=medium
    ?question_type=bac
    ?has_solution=true
    ?has_graph=true
    ?is_standalone=true
    """

    serializer_class = QuestionDetailSerializer

    def get(self, request, axis_id):
        axis = get_object_or_404(
            Axis.objects.select_related(
                "chapter",
                "chapter__subject",
            ),
            id=axis_id,
            is_active=True,
            chapter__is_active=True,
        )

        questions = (
            Question.objects
            .select_related(
                "axis",
                "axis__chapter",
                "axis__chapter__subject",
                "branch",
            )
            .filter(
                axis=axis,
                is_active=True,
            )
        )

        year = request.query_params.get(
            "year"
        )

        difficulty = request.query_params.get(
            "difficulty"
        )

        question_type = request.query_params.get(
            "question_type"
        )

        has_solution = request.query_params.get(
            "has_solution"
        )

        has_graph = request.query_params.get(
            "has_graph"
        )

        is_standalone = request.query_params.get(
            "is_standalone"
        )

        # Filtre année
        if year:
            try:
                parsed_year = int(year)
            except ValueError:
                return Response(
                    {
                        "detail": (
                            "Le paramètre year doit être "
                            "un nombre entier."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            questions = questions.filter(
                year=parsed_year,
            )

        # Filtre difficulté
        if difficulty:
            allowed_difficulties = {
                choice[0]
                for choice in Question.DIFFICULTY_CHOICES
            }

            if difficulty not in allowed_difficulties:
                return Response(
                    {
                        "detail": (
                            "difficulty doit être easy, "
                            "medium ou hard."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            questions = questions.filter(
                difficulty=difficulty,
            )

        # Filtre type de question
        if question_type:
            allowed_types = {
                choice[0]
                for choice in Question.QUESTION_TYPE_CHOICES
            }

            if question_type not in allowed_types:
                return Response(
                    {
                        "detail": (
                            "question_type doit être bac, "
                            "guided, practice ou quiz."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            questions = questions.filter(
                question_type=question_type,
            )

        # Filtre présence de solution
        if has_solution is not None:
            normalized_has_solution = (
                has_solution
                .strip()
                .lower()
            )

            if normalized_has_solution in {
                "true",
                "1",
                "yes",
            }:
                questions = questions.exclude(
                    solution={},
                )

            elif normalized_has_solution in {
                "false",
                "0",
                "no",
            }:
                questions = questions.filter(
                    Q(solution={})
                    | Q(solution__isnull=True)
                )

            else:
                return Response(
                    {
                        "detail": (
                            "has_solution doit être "
                            "true ou false."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filtre présence de graphe
        if has_graph is not None:
            normalized_has_graph = (
                has_graph
                .strip()
                .lower()
            )

            if normalized_has_graph in {
                "true",
                "1",
                "yes",
            }:
                questions = questions.exclude(
                    graph_data={},
                )

            elif normalized_has_graph in {
                "false",
                "0",
                "no",
            }:
                questions = questions.filter(
                    Q(graph_data={})
                    | Q(graph_data__isnull=True)
                )

            else:
                return Response(
                    {
                        "detail": (
                            "has_graph doit être "
                            "true ou false."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filtre question autonome
        if is_standalone is not None:
            normalized_is_standalone = (
                is_standalone
                .strip()
                .lower()
            )

            if normalized_is_standalone in {
                "true",
                "1",
                "yes",
            }:
                questions = questions.filter(
                    is_standalone=True,
                )

            elif normalized_is_standalone in {
                "false",
                "0",
                "no",
            }:
                questions = questions.filter(
                    is_standalone=False,
                )

            else:
                return Response(
                    {
                        "detail": (
                            "is_standalone doit être "
                            "true ou false."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        questions = questions.order_by(
            "year",
            "order",
            "number",
            "id",
        )

        serializer = self.get_serializer(
            questions,
            many=True,
        )

        axis_data = AxisSummarySerializer(
            axis,
            context=self.get_serializer_context(),
        ).data

        return Response(
            {
                "axis": axis_data,
                "filters": {
                    "year": year,
                    "difficulty": difficulty,
                    "question_type": question_type,
                    "has_solution": has_solution,
                    "has_graph": has_graph,
                    "is_standalone": is_standalone,
                },
                "count": questions.count(),
                "questions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class QuestionDetailView(BaseStudentAPIView):
    """
    Retourne une question avec sa solution JSON.

    URL :
    GET /api/course/questions/<question_id>/
    """

    serializer_class = QuestionDetailSerializer

    def get(self, request, question_id):
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

        serializer = self.get_serializer(
            question,
        )

        return Response(
            {
                "question": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AxisQuestionSummaryListView(BaseStudentAPIView):
    """
    Retourne une version légère des questions d'un axe.

    La solution complète n'est pas retournée.

    URL :
    GET /api/course/axes/<axis_id>/questions/summary/
    """

    serializer_class = QuestionSummarySerializer

    def get(self, request, axis_id):
        axis = get_object_or_404(
            Axis.objects.select_related(
                "chapter",
                "chapter__subject",
            ),
            id=axis_id,
            is_active=True,
            chapter__is_active=True,
        )

        questions = (
            Question.objects
            .select_related(
                "axis",
                "branch",
            )
            .filter(
                axis=axis,
                is_active=True,
            )
            .order_by(
                "year",
                "order",
                "number",
                "id",
            )
        )

        serializer = self.get_serializer(
            questions,
            many=True,
        )

        return Response(
            {
                "axis": AxisSummarySerializer(
                    axis,
                    context=self.get_serializer_context(),
                ).data,
                "count": questions.count(),
                "questions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class QuestionCreateView(BaseStudentAPIView):
    """
    Crée une question avec une solution JSON directe.

    URL :
    POST /api/course/questions/create/
    """

    serializer_class = QuestionWriteSerializer

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        question = serializer.save()

        response_serializer = QuestionDetailSerializer(
            question,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "detail": "Question créée avec succès.",
                "question": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class QuestionUpdateView(BaseStudentAPIView):
    """
    Modifie une question et sa solution JSON.

    URL :
    PATCH /api/course/questions/<question_id>/update/
    PUT /api/course/questions/<question_id>/update/
    """

    serializer_class = QuestionWriteSerializer

    def get_question(self, question_id):
        return get_object_or_404(
            Question.objects.select_related(
                "axis",
                "axis__chapter",
                "axis__chapter__subject",
                "branch",
            ),
            id=question_id,
        )

    def patch(self, request, question_id):
        question = self.get_question(
            question_id,
        )

        serializer = self.get_serializer(
            question,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        question = serializer.save()

        response_serializer = QuestionDetailSerializer(
            question,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "detail": "Question modifiée avec succès.",
                "question": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, question_id):
        question = self.get_question(
            question_id,
        )

        serializer = self.get_serializer(
            question,
            data=request.data,
            partial=False,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        question = serializer.save()

        response_serializer = QuestionDetailSerializer(
            question,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "detail": "Question remplacée avec succès.",
                "question": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class QuestionDeleteView(BaseStudentAPIView):
    """
    Désactive une question sans la supprimer définitivement.

    URL :
    DELETE /api/course/questions/<question_id>/delete/
    """

    def delete(self, request, question_id):
        question = get_object_or_404(
            Question,
            id=question_id,
        )

        question.is_active = False

        question.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        return Response(
            {
                "detail": "Question désactivée avec succès."
            },
            status=status.HTTP_200_OK,
        )







import logging

from django.shortcuts import get_object_or_404

from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course.models import Axis



logger = logging.getLogger(__name__)


class ReExplainStepAPIView(
    GenericAPIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    serializer_class = (
        ReExplainStepRequestSerializer
    )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="step_id",
                type=str,
                required=False,
                location=(
                    OpenApiParameter.QUERY
                ),
                description=(
                    "معرف المرحلة لجلب "
                    "شروحاتها فقط."
                ),
            ),
            OpenApiParameter(
                name="axis_id",
                type=int,
                required=False,
                location=(
                    OpenApiParameter.QUERY
                ),
                description=(
                    "معرف المحور لمنع خلط "
                    "شروحات المحاور المختلفة."
                ),
            ),
        ],
        responses={
            200: (
                ReExplainStepHistoryListResponseSerializer
            ),
        },
    )
    def get(self, request):
        step_id = str(
            request.query_params.get(
                "step_id"
            )
            or ""
        ).strip()

        axis_id_value = str(
            request.query_params.get(
                "axis_id"
            )
            or ""
        ).strip()

        axis_id = None

        if axis_id_value:
            try:
                axis_id = int(
                    axis_id_value
                )

                if axis_id < 1:
                    raise ValueError

            except ValueError:
                return Response(
                    {
                        "axis_id": [
                            (
                                "معرف المحور يجب أن "
                                "يكون عددًا صحيحًا."
                            )
                        ]
                    },
                    status=(
                        status
                        .HTTP_400_BAD_REQUEST
                    ),
                )

        histories = (
            ReExplainStepHistoryService
            .get_student_history(
                student=request.user,
                step_id=step_id or None,
                axis_id=axis_id,
            )
        )

        history_serializer = (
            ReExplainStepHistorySerializer(
                histories,
                many=True,
            )
        )

        return Response(
            {
                "step_id": step_id,
                "count": histories.count(),
                "max_explanations": (
                    ReExplainStepHistoryService
                    .MAX_EXPLANATIONS
                ),
                "results": (
                    history_serializer.data
                ),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=(
            ReExplainStepRequestSerializer
        ),
        responses={
            200: (
                ReExplainStepResponseSerializer
            ),
        },
    )
    def post(self, request):
        request_serializer = (
            self.get_serializer(
                data=request.data
            )
        )

        request_serializer.is_valid(
            raise_exception=True
        )

        validated_data = (
            request_serializer.validated_data
        )

        step = validated_data["step"]

        student_question = (
            validated_data[
                "student_question"
            ]
        )

        axis_id = validated_data[
            "axis_id"
        ]

        axis = get_object_or_404(
            Axis.objects.select_related(
                "chapter",
                "chapter__subject",
            ),
            id=axis_id,
            is_active=True,
            chapter__is_active=True,
        )

        try:
            generation_service = (
                ReExplainStepService()
            )

            generated_result = (
                generation_service.generate(
                    step=step,
                    student_question=(
                        student_question
                    ),
                )
            )

            save_result = (
                ReExplainStepHistoryService
                .save_history(
                    student=request.user,
                    axis=axis,
                    step=step,
                    student_question=(
                        student_question
                    ),
                    generated_result=(
                        generated_result
                    ),
                )
            )

            saved_history = (
                save_result["history"]
            )

            saved_serializer = (
                ReExplainStepHistorySerializer(
                    saved_history
                )
            )

            response_data = {
                **generated_result,
                "replaced_oldest": (
                    save_result[
                        "replaced_oldest"
                    ]
                ),
                "explanations_count": (
                    save_result["count"]
                ),
                "max_explanations": (
                    ReExplainStepHistoryService
                    .MAX_EXPLANATIONS
                ),
                "saved_explanation": (
                    saved_serializer.data
                ),
            }

            response_serializer = (
                ReExplainStepResponseSerializer(
                    data=response_data
                )
            )

            response_serializer.is_valid(
                raise_exception=True
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            logger.exception(
                (
                    "Erreur pendant la "
                    "ré-explication step=%s "
                    "axis=%s student=%s"
                ),
                step.get("id"),
                axis_id,
                request.user.pk,
            )

            return Response(
                {
                    "error": (
                        "حدث خطأ أثناء إعادة "
                        "شرح المرحلة."
                    ),
                    "details": str(exc),
                },
                status=(
                    status
                    .HTTP_500_INTERNAL_SERVER_ERROR
                ),
            )

