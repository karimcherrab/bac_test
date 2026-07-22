from django.urls import path
from exercise_generation.views import AxisGeneratedExercisesAPIView, ExerciseGenerateAPIView, \
    ExerciseAlternativeSolutionAPIView

app_name = "exercise_generation"

urlpatterns = [
    path("generate/", ExerciseGenerateAPIView.as_view(), name="generate"),
    path("axes/<int:axis_id>/", AxisGeneratedExercisesAPIView.as_view(), name="axis-exercises"),

    path(
        "exercises/<int:exercise_id>/alternative-solution/",
        ExerciseAlternativeSolutionAPIView.as_view(),
        name="exercise-alternative-solution",
    ),
]
