from django.urls import path

from .views import (
    AxisDetailView, ReExplainStepAPIView,
    AxisListView,
    BranchDetailView,
    BranchListView,
    ChapterDetailView,
    ChapterListView,
    SubjectDetailView,
    SubjectListView, AxisQuestionSummaryListView, AxisQuestionListView, QuestionDetailView, SubjectByBranchView,
)


app_name = "course"


urlpatterns = [
    # Filières
    path(
        "branches/",
        BranchListView.as_view(),
        name="branch-list",
    ),
    path(
        "branches/<int:branch_id>/",
        BranchDetailView.as_view(),
        name="branch-detail",
    ),

    # Matières
    path(
        "subjects/",
        SubjectListView.as_view(),
        name="subject-list",
    ),
    path(
        "subjects/<int:subject_id>/",
        SubjectDetailView.as_view(),
        name="subject-detail",
    ),

    # Chapitres
    path(
        "chapters/",
        ChapterListView.as_view(),
        name="chapter-list",
    ),
    path(
        "chapters/<int:chapter_id>/",
        ChapterDetailView.as_view(),
        name="chapter-detail",
    ),

    # Axes
    path(
        "axes/",
        AxisListView.as_view(),
        name="axis-list",
    ),
    path(
        "axes/<int:axis_id>/",
        AxisDetailView.as_view(),
        name="axis-detail",
    ),

    # Questions d'un axe avec solutions
    path(
        "axes/<int:axis_id>/questions/",
        AxisQuestionListView.as_view(),
        name="axis-question-list",
    ),

    # Version légère des questions
    path(
        "axes/<int:axis_id>/questions/summary/",
        AxisQuestionSummaryListView.as_view(),
        name="axis-question-summary-list",
    ),

    # Détail d'une question avec sa solution
    path(
        "questions/<int:question_id>/",
        QuestionDetailView.as_view(),
        name="question-detail",
    ),

    path(
        "axes/re-explication/",
        ReExplainStepAPIView.as_view(),
        name="re-explication",
    ),

    # path(
    #     "axes/re-explication/history/",
    #     ReExplainStepAPIView.as_view(),
    #     name="re-explication",
    # ),

    path(
        "subjects/my-branch/",
        SubjectByBranchView.as_view(),
        name="subjects-by-student-branch",
    ),

]