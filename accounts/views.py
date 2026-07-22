from django.contrib.auth.hashers import check_password
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Student
from .serializers import (
    LoginStudentSerializer,
    StudentResponseSerializer,
    StudentSerializer,
)


class StudentView(GenericAPIView):
    serializer_class = StudentSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        student = serializer.save()

        refresh = RefreshToken.for_user(
            student
        )

        return Response(
            {
                "message": (
                    "Compte créé avec succès"
                ),
                "student": (
                    StudentResponseSerializer(
                        student
                    ).data
                ),
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(
                        refresh.access_token
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginStudentView(GenericAPIView):
    serializer_class = LoginStudentSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        email = serializer.validated_data[
            "email"
        ]

        password = serializer.validated_data[
            "password"
        ]

        try:
            student = (
                Student.objects
                .select_related("branch")
                .get(email__iexact=email)
            )
        except Student.DoesNotExist:
            return Response(
                {
                    "detail": (
                        "Aucun étudiant ne correspond "
                        "à cet email."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not student.is_active:
            return Response(
                {
                    "detail": (
                        "Ce compte étudiant est désactivé."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not check_password(
            password,
            student.password,
        ):
            return Response(
                {
                    "detail": (
                        "Mot de passe incorrect."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(
            student
        )

        return Response(
            {
                "message": (
                    "Connexion réussie"
                ),
                "student": (
                    StudentResponseSerializer(
                        student
                    ).data
                ),
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(
                        refresh.access_token
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )