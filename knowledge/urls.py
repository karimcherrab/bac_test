from django.urls import path,include
from .views import chaptersView, AxisByChapterView, TutorAPIView, ExplainCourAPIView, SessionsView, \
    QuestionBacByAxisView, SolveBacExerciseAPIView, SessionMessagesAPIView, TutorChatAPIView

urlpatterns = [
    path('chapters/',chaptersView.as_view(),name='chapters'),
    path("chapters/<int:chapter_id>/axes/",AxisByChapterView.as_view(),name="axis-by-chapter"),
    path("tutor/", TutorAPIView.as_view(), name="tutor-api"),
    path("axes/<int:axis_id>/<str:type_data>/", QuestionBacByAxisView.as_view(), name="questions-by-axis"),
    path("bac-exercises/solve/",SolveBacExerciseAPIView.as_view(),name="solve-bac-exercise"),
    path("explain-cour/", ExplainCourAPIView.as_view(), name="explain-cour"),
    path(    "sessions/<uuid:session_id>/messages/",     SessionMessagesAPIView.as_view(), ),
    # path("session/", SessionsView.as_view(), name="session"),
    path("session/<str:current_chapter>/", SessionsView.as_view()),
    # path('features/<int:pk>',featureDetailView.as_view(),name='feature-detail'),
    #
    # path('plans',planView.as_view(),name='plans'),
    # path('plans/<int:pk>',planDetailView.as_view(),name='plan-detail'),
    #
    # path('subscriptions',subscriptionView.as_view(),name='subscriptions'),
    #
    # path('webhook/clickpay/<str:owner_id>',subscriptionWebhook.as_view(),name='click-webhook'),

    path(
        "tutor/chat/",
        TutorChatAPIView.as_view(),
        name="tutor-chat",
    ),
]
