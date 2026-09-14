from django.urls import path
from .views import Lessons,Generate,Detail,Answer,History,Context,Exercises
app_name='memory_practice'
urlpatterns=[path("exercises/",Exercises.as_view()),path('context/',Context.as_view()),path('lessons/',Lessons.as_view()),path('generate/',Generate.as_view()),path('history/',History.as_view()),path('questions/<int:pk>/',Detail.as_view()),path('questions/<int:pk>/answer/',Answer.as_view())]
