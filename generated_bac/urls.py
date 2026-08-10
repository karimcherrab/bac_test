from django.urls import path

from .views import (
    GenerateBacExerciseAPIView,
    GenerateBacSolutionAPIView,
    GeneratedBacExerciseDetailAPIView,
    MyGeneratedBacExercisesAPIView,
    ReExplainBacQuestionSolutionAPIView,
)

app_name = "generated_bac"

urlpatterns = [
    path(
        "generate/",
        GenerateBacExerciseAPIView.as_view(),
        name="generate-exercise",
    ),
    path(
        "my-exercises/",
        MyGeneratedBacExercisesAPIView.as_view(),
        name="my-exercises",
    ),
    path(
        "<int:exercise_id>/",
        GeneratedBacExerciseDetailAPIView.as_view(),
        name="exercise-detail",
    ),
    path(
        "<int:exercise_id>/generate-solution/",
        GenerateBacSolutionAPIView.as_view(),
        name="generate-solution",
    ),
    path(
        "<int:exercise_id>/questions/<str:question_id>/re-explain-solution/",
        ReExplainBacQuestionSolutionAPIView.as_view(),
        name="re-explain-question-solution",
    ),
]
