from django.urls import path

from exercise_bac.views import ExerciseBacByChapterView
from exercise_bac.views_step import BacStepReExplanationAPIView

app_name = "exercise_bac"


urlpatterns = [
    path(
        "chapter/<int:chapter_id>/",
        ExerciseBacByChapterView.as_view(),
        name="exercise-bac-by-chapter",
    ),

    path(
        "re-explain-step/",
        BacStepReExplanationAPIView.as_view(),
        name="bac-step-re-explanation",
    ),
]