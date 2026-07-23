from django.urls import path

from .views import (
    AxisRevisionByTagAPIView,
    AxisRevisionDetailAPIView,
    ChapterAxisRevisionListAPIView,
)


app_name = "axis_revision"


urlpatterns = [
    path(
        "axes/<int:axis_id>/revision/",
        AxisRevisionDetailAPIView.as_view(),
        name="axis-revision-detail",
    ),

    path(
        "axes/tag/<slug:axis_tag>/revision/",
        AxisRevisionByTagAPIView.as_view(),
        name="axis-revision-by-tag",
    ),

    path(
        "chapters/<int:chapter_id>/revisions/",
        ChapterAxisRevisionListAPIView.as_view(),
        name="chapter-revisions",
    ),
]