from django.urls import path

from .views import (
    CloseSessionAPIView,
    CurrentSessionAPIView,
    SessionMessagesAPIView,
    TutorChatAPIView,
)

app_name = "tutor_chat"

urlpatterns = [
    path("chat/", TutorChatAPIView.as_view(), name="chat"),
    path(
        "sessions/current/<int:chapter_id>/",
        CurrentSessionAPIView.as_view(),
        name="current-session",
    ),
    path(
        "sessions/<uuid:session_id>/messages/",
        SessionMessagesAPIView.as_view(),
        name="session-messages",
    ),
    path(
        "sessions/<uuid:session_id>/close/",
        CloseSessionAPIView.as_view(),
        name="close-session",
    ),
]
