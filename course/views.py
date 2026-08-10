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


from django.shortcuts import (
    get_object_or_404,
)

from rest_framework import status

from rest_framework.response import (
    Response,
)

from course.models import Subject

from course.serializers import (
    SubjectDetailSerializer,
)



class SubjectDetailView(
    BaseStudentAPIView,
):
    serializer_class = SubjectDetailSerializer

    def get(
        self,
        request,
        subject_id,
    ):
        subject = get_object_or_404(
            Subject,
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

    def get(self, request, subject_id):
        chapters = (
            Chapter.objects
            .select_related(
                "subject",
            )
            .prefetch_related(
                "axes",
            )
            .filter(
                subject_id=subject_id,
                is_active=True,
            )
            .distinct()
            .order_by(
                "order",
                "title",
            )
        )

        serializer = self.get_serializer(
            chapters,
            many=True,
        )

        return Response(
            {
                "subject_id": subject_id,
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

    def get(
        self,
        request,
        chapter_id,
        branch_code,
    ):
        axes = (
            Axis.objects
            .select_related(
                "chapter",
                "chapter__subject",
            )
            .prefetch_related(
                "branches",
            )
            .filter(
                chapter_id=chapter_id,
                branches__code=branch_code,
                is_active=True,
                chapter__is_active=True,
            )
            .distinct()
            .order_by(
                "chapter__order",
                "order",
                "title",
            )
        )

        serializer = self.get_serializer(
            axes,
            many=True,
        )

        return Response(
            {
                "filters": {
                    "chapter_id": chapter_id,
                    "branch_code": branch_code,
                },
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
    Retourne toutes les questions d'un axe avec :

    - solution
    - graph_data
    - documents

    URL :
    GET /api/course/axes/<axis_id>/questions/

    Filtres :
    ?year=2025
    ?difficulty=medium
    ?question_type=bac
    ?has_solution=true
    ?has_graph=true
    ?has_documents=true
    ?is_standalone=true
    """

    serializer_class = QuestionDetailSerializer

    TRUE_VALUES = {
        "true",
        "1",
        "yes",
        "oui",
    }

    FALSE_VALUES = {
        "false",
        "0",
        "no",
        "non",
    }

    def parse_boolean_param(
        self,
        value,
        parameter_name,
    ):
        """
        Convertit un paramètre query en bool.

        Retourne :
        - True
        - False
        - None si paramètre absent

        Lève ValueError si valeur invalide.
        """

        if value is None:
            return None

        normalized = (
            str(value)
            .strip()
            .lower()
        )

        if normalized in self.TRUE_VALUES:
            return True

        if normalized in self.FALSE_VALUES:
            return False

        raise ValueError(
            f"{parameter_name} doit être true ou false."
        )

    def get(self, request, axis_id):
        # =====================================================
        # AXIS
        # =====================================================

        axis = get_object_or_404(
            Axis.objects.select_related(
                "chapter",
                "chapter__subject",
            ),
            id=axis_id,
            is_active=True,
            chapter__is_active=True,
        )

        # =====================================================
        # QUERYSET
        # =====================================================

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

        # =====================================================
        # PARAMS
        # =====================================================

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

        has_documents = request.query_params.get(
            "has_documents"
        )

        is_standalone = request.query_params.get(
            "is_standalone"
        )

        # =====================================================
        # YEAR
        # =====================================================

        if year:
            try:
                parsed_year = int(year)

            except (
                TypeError,
                ValueError,
            ):
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

        # =====================================================
        # DIFFICULTY
        # =====================================================

        if difficulty:
            difficulty = (
                difficulty
                .strip()
                .lower()
            )

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

        # =====================================================
        # QUESTION TYPE
        # =====================================================

        if question_type:
            question_type = (
                question_type
                .strip()
                .lower()
            )

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

        # =====================================================
        # HAS SOLUTION
        # =====================================================

        try:
            parsed_has_solution = (
                self.parse_boolean_param(
                    has_solution,
                    "has_solution",
                )
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parsed_has_solution is True:
            questions = (
                questions
                .exclude(
                    solution={},
                )
                .exclude(
                    solution__isnull=True,
                )
            )

        elif parsed_has_solution is False:
            questions = questions.filter(
                Q(solution={})
                | Q(solution__isnull=True)
            )

        # =====================================================
        # HAS GRAPH
        # =====================================================

        try:
            parsed_has_graph = (
                self.parse_boolean_param(
                    has_graph,
                    "has_graph",
                )
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parsed_has_graph is True:
            questions = (
                questions
                .exclude(
                    graph_data={},
                )
                .exclude(
                    graph_data__isnull=True,
                )
            )

        elif parsed_has_graph is False:
            questions = questions.filter(
                Q(graph_data={})
                | Q(graph_data__isnull=True)
            )

        # =====================================================
        # HAS DOCUMENTS
        # =====================================================

        try:
            parsed_has_documents = (
                self.parse_boolean_param(
                    has_documents,
                    "has_documents",
                )
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parsed_has_documents is not None:
            questions = self.filter_by_documents(
                questions=questions,
                has_documents=parsed_has_documents,
            )

        # =====================================================
        # IS STANDALONE
        # =====================================================

        try:
            parsed_is_standalone = (
                self.parse_boolean_param(
                    is_standalone,
                    "is_standalone",
                )
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parsed_is_standalone is not None:
            questions = questions.filter(
                is_standalone=parsed_is_standalone,
            )

        # =====================================================
        # ORDER
        # =====================================================

        questions = questions.order_by(
            "year",
            "order",
            "number",
            "id",
        )

        # Important :
        # évaluer le queryset une seule fois.
        questions_list = list(
            questions
        )

        # =====================================================
        # SERIALIZATION
        # =====================================================

        serializer = self.get_serializer(
            questions_list,
            many=True,
        )

        axis_data = AxisSummarySerializer(
            axis,
            context=self.get_serializer_context(),
        ).data

        # =====================================================
        # DOCUMENT STATS
        # =====================================================

        questions_with_documents = sum(
            1
            for question in questions_list
            if self.question_has_documents(
                question
            )
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return Response(
            {
                "axis": axis_data,

                "filters": {
                    "year": year,
                    "difficulty": difficulty,
                    "question_type": question_type,
                    "has_solution": has_solution,
                    "has_graph": has_graph,
                    "has_documents": has_documents,
                    "is_standalone": is_standalone,
                },

                "count": len(
                    questions_list
                ),

                "documents_stats": {
                    "with_documents": (
                        questions_with_documents
                    ),
                    "without_documents": (
                        len(questions_list)
                        - questions_with_documents
                    ),
                },

                "questions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    # =========================================================
    # DOCUMENT HELPERS
    # =========================================================

    def get_question_documents(
        self,
        question,
    ):
        """
        Même logique que le serializer.

        Supporte :
        - Question.documents
        - metadata["documents"]
        """

        if hasattr(
            question,
            "documents",
        ):
            documents = getattr(
                question,
                "documents",
                None,
            )

            if isinstance(
                documents,
                list,
            ):
                return documents

        metadata = getattr(
            question,
            "metadata",
            None,
        )

        if isinstance(
            metadata,
            dict,
        ):
            documents = metadata.get(
                "documents",
                [],
            )

            if isinstance(
                documents,
                list,
            ):
                return documents

        return []

    def question_has_documents(
        self,
        question,
    ):
        return bool(
            self.get_question_documents(
                question
            )
        )

    def filter_by_documents(
        self,
        questions,
        has_documents,
    ):
        """
        Fonctionne même si documents est uniquement
        stocké dans metadata.

        Comme metadata contient du JSON complexe,
        on récupère les IDs puis on filtre le queryset.
        """

        matching_ids = []

        for question in questions.only(
            "id",
            "metadata",
        ):
            documents = (
                self.get_question_documents(
                    question
                )
            )

            current_has_documents = bool(
                documents
            )

            if (
                current_has_documents
                == has_documents
            ):
                matching_ids.append(
                    question.id
                )

        return questions.filter(
            id__in=matching_ids,
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


import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiParameter, extend_schema

from course.models import Axis

logger = logging.getLogger(__name__)


class ReExplainStepAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReExplainStepRequestSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name="step_id", type=str, required=False, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="axis_id", type=int, required=False, location=OpenApiParameter.QUERY),
        ],
        responses={200: ReExplainStepHistoryListResponseSerializer},
    )
    def get(self, request):
        step_id = str(request.query_params.get("step_id") or "").strip()
        raw_axis_id = str(request.query_params.get("axis_id") or "").strip()
        axis_id = None
        if raw_axis_id:
            try:
                axis_id = int(raw_axis_id)
                if axis_id < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response({"axis_id": ["معرف المحور يجب أن يكون عددًا صحيحًا موجبًا."]}, status=400)

        histories = ReExplainStepHistoryService.get_student_history(
            student=request.user, step_id=step_id or None, axis_id=axis_id
        )
        return Response({
            "step_id": step_id,
            "axis_id": axis_id,
            "count": histories.count(),
            "max_explanations": ReExplainStepHistoryService.MAX_EXPLANATIONS,
            "results": ReExplainStepHistorySerializer(histories, many=True).data,
        })

    @extend_schema(request=ReExplainStepRequestSerializer, responses={200: ReExplainStepResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        axis = get_object_or_404(
            Axis.objects.select_related("chapter", "chapter__subject"),
            id=data["axis_id"], is_active=True, chapter__is_active=True,
        )

        try:
            generated = ReExplainStepService().generate(
                step=data["step"],
                student_question=data["student_question"],
                request_type=data["request_type"],
            )
            saved = ReExplainStepHistoryService.save_history(
                student=request.user,
                axis=axis,
                step=data["step"],
                student_question=data["student_question"],
                generated_result=generated,
            )
            response_data = {
                **generated,
                "replaced_oldest": saved["replaced_oldest"],
                "explanations_count": saved["count"],
                "max_explanations": ReExplainStepHistoryService.MAX_EXPLANATIONS,
                "saved_explanation": ReExplainStepHistorySerializer(saved["history"]).data,
            }
            output = ReExplainStepResponseSerializer(data=response_data)
            output.is_valid(raise_exception=True)
            return Response(output.data, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception(
                "Re-explanation failed step=%s axis=%s student=%s",
                data["step"].get("id"), data["axis_id"], request.user.pk,
            )
            # لا نرسل تفاصيل الاستثناء الداخلية إلى الواجهة في production.
            return Response(
                {"error": "حدث خطأ أثناء إنشاء الشرح. أعد المحاولة."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# AI - حل سؤال Question بطريقة شديدة التبسيط + الحفظ للطالب
# ============================================================

from django.db import transaction

from .models import StudentQuestionSimpleSolution
from .serializers import (
    QuestionSimpleSolutionRequestSerializer,
    QuestionSimpleSolutionResponseSerializer,
)
from .resolution.simple_solution_service import (
    SimpleQuestionSolutionError,
    SimpleQuestionSolutionParsingError,
    SimpleQuestionSolutionService,
)


class QuestionSimpleSolutionAPIView(BaseStudentAPIView):
    """
    GET /api/course/questions/<question_id>/simple-solution/
        يرجع الحل المبسط المحفوظ للطالب الحالي إن وجد.

    POST /api/course/questions/<question_id>/simple-solution/
        body اختياري:
        {"regenerate": false}

        - إذا كان الحل محفوظًا و regenerate=false: يعيد المحفوظ بدون AI.
        - إذا لم يوجد حل: يولد حلاً ويحفظه.
        - إذا regenerate=true: يولد حلاً جديدًا ويحدث السجل المحفوظ.
    """

    serializer_class = QuestionSimpleSolutionRequestSerializer

    @staticmethod
    def _get_question(question_id):
        return get_object_or_404(
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

    def _build_response_data(
        self,
        *,
        question,
        saved_solution=None,
        source="none",
    ):
        exists = saved_solution is not None

        response_data = {
            "success": True,
            "exists": exists,
            "saved": exists,
            "source": source if exists else "none",
            "question_id": question.id,
            "subject": question.axis.chapter.subject.name,
            "model": (
                saved_solution.model_name
                if saved_solution is not None
                else ""
            ),
            "simple_solution": (
                saved_solution.solution
                if saved_solution is not None
                else None
            ),
            "created_at": (
                saved_solution.created_at
                if saved_solution is not None
                else None
            ),
            "updated_at": (
                saved_solution.updated_at
                if saved_solution is not None
                else None
            ),
        }

        output = QuestionSimpleSolutionResponseSerializer(
            data=response_data,
        )
        output.is_valid(raise_exception=True)
        return output.data

    @extend_schema(
        responses={200: QuestionSimpleSolutionResponseSerializer},
    )
    def get(self, request, question_id):
        question = self._get_question(question_id)

        saved_solution = (
            StudentQuestionSimpleSolution.objects
            .filter(
                student=request.user,
                question=question,
            )
            .first()
        )

        return Response(
            self._build_response_data(
                question=question,
                saved_solution=saved_solution,
                source="saved" if saved_solution else "none",
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=QuestionSimpleSolutionRequestSerializer,
        responses={
            200: QuestionSimpleSolutionResponseSerializer,
            201: QuestionSimpleSolutionResponseSerializer,
        },
    )
    def post(self, request, question_id):
        serializer = self.get_serializer(
            data=request.data or {},
        )
        serializer.is_valid(raise_exception=True)

        regenerate = serializer.validated_data.get(
            "regenerate",
            False,
        )

        question = self._get_question(question_id)

        existing = (
            StudentQuestionSimpleSolution.objects
            .filter(
                student=request.user,
                question=question,
            )
            .first()
        )

        # مهم: إذا كان الحل موجودًا لا نستدعي AI مرة أخرى.
        if existing is not None and not regenerate:
            return Response(
                self._build_response_data(
                    question=question,
                    saved_solution=existing,
                    source="saved",
                ),
                status=status.HTTP_200_OK,
            )

        try:
            generated = SimpleQuestionSolutionService().generate(
                question=question,
            )

            with transaction.atomic():
                saved_solution, created = (
                    StudentQuestionSimpleSolution.objects
                    .update_or_create(
                        student=request.user,
                        question=question,
                        defaults={
                            "solution": generated.solution,
                            "model_name": generated.model_name,
                            "raw_response": generated.raw_response,
                        },
                    )
                )

            return Response(
                self._build_response_data(
                    question=question,
                    saved_solution=saved_solution,
                    source="generated",
                ),
                status=(
                    status.HTTP_201_CREATED
                    if created
                    else status.HTTP_200_OK
                ),
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
