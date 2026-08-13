import logging

from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.generics import (
    GenericAPIView,
)
from rest_framework.permissions import (
    AllowAny, IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import (
    RefreshToken,
)

from .authentication import StudentJWTAuthentication
from .email_verification import (
    ExpiredVerificationToken,
    InvalidVerificationToken,
    decode_email_verification_token,
    send_student_verification_email,
)
from .models import Student
from .serializers import (
    LoginStudentSerializer,
    ResendVerificationEmailSerializer,
    StudentResponseSerializer,
    StudentSerializer,
    VerifyEmailSerializer, UpdateStudentNameSerializer, ChangeStudentPasswordSerializer,
)


logger = logging.getLogger(__name__)


class StudentView(GenericAPIView):
    serializer_class = StudentSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        student = serializer.save()

        try:
            send_student_verification_email(
                student
            )

        except Exception:
            logger.exception(
                (
                    "Impossible d'envoyer l'email "
                    "de vérification à %s"
                ),
                student.email,
            )

            # بما أننا داخل transaction.atomic،
            # سيُلغي إنشاء الحساب بالكامل.
            raise

        return Response(
            {
                "message": (
                    "Compte créé avec succès. "
                    "Un lien de vérification a été "
                    "envoyé à votre adresse email."
                ),
                "requires_email_verification": True,
                "email": student.email,
                "student": (
                    StudentResponseSerializer(
                        student
                    ).data
                ),

                # لا نرسل tokens قبل التفعيل
                "tokens": None,
            },
            status=status.HTTP_201_CREATED,
        )
class VerifyStudentEmailView(
    GenericAPIView
):
    serializer_class = VerifyEmailSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        token = serializer.validated_data[
            "token"
        ]

        try:
            payload = (
                decode_email_verification_token(
                    token
                )
            )

        except ExpiredVerificationToken:
            return Response(
                {
                    "message": (
                        "Le lien de vérification "
                        "a expiré."
                    ),
                    "code": "verification_link_expired",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except InvalidVerificationToken:
            return Response(
                {
                    "message": (
                        "Le lien de vérification "
                        "est invalide."
                    ),
                    "code": "invalid_verification_link",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        student_id = payload.get(
            "student_id"
        )

        token_email = (
            payload.get("email", "")
            .strip()
            .lower()
        )

        if not student_id or not token_email:
            return Response(
                {
                    "message": (
                        "Le lien de vérification "
                        "est incomplet."
                    ),
                    "code": "invalid_verification_link",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student = (
                Student.objects
                .select_for_update()
                .select_related("branch")
                .get(
                    pk=student_id,
                    email__iexact=token_email,
                )
            )

        except Student.DoesNotExist:
            return Response(
                {
                    "message": (
                        "Le compte associé à ce lien "
                        "n'existe pas."
                    ),
                    "code": "student_not_found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if student.is_active:
            return Response(
                {
                    "message": (
                        "Votre adresse email est "
                        "déjà vérifiée."
                    ),
                    "already_verified": True,
                    "student": (
                        StudentResponseSerializer(
                            student
                        ).data
                    ),
                },
                status=status.HTTP_200_OK,
            )

        student.is_active = True
        student.email_verified_at = timezone.now()

        student.save(
            update_fields=[
                "is_active",
                "email_verified_at",
                "updated_at",
            ]
        )

        return Response(
            {
                "message": (
                    "Votre adresse email a été "
                    "vérifiée avec succès. "
                    "Vous pouvez maintenant "
                    "vous connecter."
                ),
                "already_verified": False,
                "student": (
                    StudentResponseSerializer(
                        student
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )
class ResendStudentVerificationView(
    GenericAPIView
):
    serializer_class = (
        ResendVerificationEmailSerializer
    )

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

        student = (
            Student.objects
            .filter(
                email__iexact=email,
            )
            .first()
        )


        generic_response = {
            "message": (
                "Si un compte non vérifié "
                "correspond à cette adresse, "
                "un nouveau lien a été envoyé."
            )
        }

        if student is None:
            return Response(
                generic_response,
                status=status.HTTP_200_OK,
            )

        if student.is_active:
            return Response(
                {
                    "message": (
                        "Cette adresse email est "
                        "déjà vérifiée."
                    ),
                    "already_verified": True,
                },
                status=status.HTTP_200_OK,
            )

        try:
            send_student_verification_email(
                student
            )

        except Exception:
            logger.exception(
                (
                    "Impossible de renvoyer "
                    "l'email de vérification à %s"
                ),
                student.email,
            )

            return Response(
                {
                    "message": (
                        "Impossible d'envoyer "
                        "l'email pour le moment."
                    )
                },
                status=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
            )

        return Response(
            {
                **generic_response,
                "already_verified": False,
            },
            status=status.HTTP_200_OK,
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

        student = serializer.validated_data[
            "student"
        ]

        refresh = RefreshToken.for_user(
            student
        )

        return Response(
            {
                "message": (
                    "Connexion réussie."
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





class StudentProfileView(
    GenericAPIView
):
    """
    جلب معلومات الطالب المتصل.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    authentication_classes = [
        StudentJWTAuthentication,
    ]

    def get(self, request):
        student = (
            Student.objects
            .select_related("branch")
            .get(pk=request.user.pk)
        )

        return Response(
            {
                "student": (
                    StudentResponseSerializer(
                        student
                    ).data
                )
            },
            status=status.HTTP_200_OK,
        )


class UpdateStudentNameView(
    GenericAPIView
):
    """
    تغيير اسم الطالب.
    """

    serializer_class = (
        UpdateStudentNameSerializer
    )

    permission_classes = [
        IsAuthenticated,
    ]

    authentication_classes = [
        StudentJWTAuthentication,
    ]

    @transaction.atomic
    def patch(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True,
        )

        student = serializer.save()

        return Response(
            {
                "message": (
                    "Votre nom a été modifié avec succès."
                ),
                "student": (
                    StudentResponseSerializer(
                        student
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )


class ChangeStudentPasswordView(
    GenericAPIView
):
    """
    تغيير كلمة مرور الطالب.
    """

    serializer_class = (
        ChangeStudentPasswordSerializer
    )

    permission_classes = [
        IsAuthenticated,
    ]

    authentication_classes = [
        StudentJWTAuthentication,
    ]

    @transaction.atomic
    def patch(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True,
        )

        serializer.save()

        return Response(
            {
                "message": (
                    "Votre mot de passe a été modifié avec succès."
                )
            },
            status=status.HTTP_200_OK,
        )