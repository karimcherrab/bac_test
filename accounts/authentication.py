from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import (
    JWTAuthentication,
)

from .models import Student


class StudentJWTAuthentication(
    JWTAuthentication
):
    """
    مصادقة JWT مخصصة لنموذج Student.

    SimpleJWT يحاول افتراضيًا جلب User من AUTH_USER_MODEL،
    لكننا هنا نستعمل نموذج Student مستقل.
    """

    def get_user(self, validated_token):
        try:
            student_id = validated_token[
                "user_id"
            ]

        except KeyError:
            raise AuthenticationFailed(
                "Le token ne contient pas l'identifiant de l'étudiant.",
                code="token_not_valid",
            )

        try:
            student = (
                Student.objects
                .select_related("branch")
                .get(pk=student_id)
            )

        except Student.DoesNotExist:
            raise AuthenticationFailed(
                "Étudiant introuvable.",
                code="student_not_found",
            )

        if not student.is_active:
            raise AuthenticationFailed(
                "Ce compte n'est pas actif.",
                code="student_inactive",
            )

        return student