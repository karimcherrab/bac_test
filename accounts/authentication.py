# accounts/authentication.py

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Student


class StudentJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        student_id = validated_token.get("user_id")

        if student_id is None:
            raise AuthenticationFailed("Token invalid: user_id manquant")

        try:
            return Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise AuthenticationFailed("Student not found")