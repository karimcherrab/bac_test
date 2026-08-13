from django.urls import path

from tutor.views import (
    TutorChatAPIView,
    TutorChatSessionListAPIView,
    TutorChatSessionDetailAPIView,
)


urlpatterns = [
    path(
        "chat/",
        TutorChatAPIView.as_view(),
        name="tutor-chat",
    ),

    path(
        "sessions/",
        TutorChatSessionListAPIView.as_view(),
        name="tutor-chat-sessions",
    ),

    path(
        "sessions/<uuid:session_id>/",
        TutorChatSessionDetailAPIView.as_view(),
        name="tutor-chat-session-detail",
    ),
]