from django.urls import include, path

urlpatterns = [
    # ... existing urls
    path("api/tutor-chat/", include("tutor_chat.urls")),
]
