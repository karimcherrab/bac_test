from django.urls import path,include
from .views import StudentView , LoginStudentView


urlpatterns = [
    path('signup/',StudentView.as_view(),name='signup'),
    path('login/' ,LoginStudentView.as_view(),name= "login")
    ]