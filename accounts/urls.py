from django.urls import path

from .views import (
    ChangeStudentPasswordView,
    LoginStudentView,
    ResendStudentVerificationView,
    StudentProfileView,
    StudentView,
    UpdateStudentNameView,
    VerifyStudentEmailView,
)


app_name = "accounts"


urlpatterns = [
    path(
        "signup/",
        StudentView.as_view(),
        name="student-signup",
    ),

    path(
        "login/",
        LoginStudentView.as_view(),
        name="student-login",
    ),

    path(
        "verify-email/",
        VerifyStudentEmailView.as_view(),
        name="verify-email",
    ),

    path(
        "resend-verification/",
        ResendStudentVerificationView.as_view(),
        name="resend-verification",
    ),

    path(
        "me/",
        StudentProfileView.as_view(),
        name="student-profile",
    ),

    path(
        "settings/name/",
        UpdateStudentNameView.as_view(),
        name="update-student-name",
    ),

    path(
        "settings/password/",
        ChangeStudentPasswordView.as_view(),
        name="change-student-password",
    ),
]