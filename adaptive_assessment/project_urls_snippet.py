# In the main project urls.py:
from django.urls import include, path

urlpatterns = [
    path(
        "api/adaptive-assessment/",
        include("adaptive_assessment.urls"),
    ),
]
