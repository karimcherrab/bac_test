from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from rest_framework import serializers

from course.models import Branch

from .models import Student


class StudentBranchSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Branch
        fields = [
            "id",
            "code",
            "name",
        ]


class StudentSerializer(
    serializers.ModelSerializer
):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    branch = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Branch.objects.all(),
    )

    class Meta:
        model = Student
        fields = [
            "id",
            "username",
            "email",
            "password",
            "branch",
            "is_active",
            "email_verified_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "is_active",
            "email_verified_at",
            "created_at",
            "updated_at",
        ]

    def validate_username(self, value):
        username = value.strip()

        if len(username) < 2:
            raise serializers.ValidationError(
                "Le nom doit contenir au moins 2 caractères."
            )

        if len(username) > 100:
            raise serializers.ValidationError(
                "Le nom ne peut pas dépasser 100 caractères."
            )

        return username

    def validate_email(self, value):
        email = value.strip().lower()

        if Student.objects.filter(
            email__iexact=email,
        ).exists():
            raise serializers.ValidationError(
                "Un compte utilisant cette adresse email existe déjà."
            )

        return email

    def validate_branch(self, value):
        if not value:
            raise serializers.ValidationError(
                "La branche est obligatoire."
            )

        return value

    def create(self, validated_data):
        password = validated_data.pop(
            "password"
        )

        student = Student(
            is_active=True,
            **validated_data,
        )

        student.set_password(password)
        student.save()

        return student


class StudentResponseSerializer(
    serializers.ModelSerializer
):
    branch = StudentBranchSerializer(
        read_only=True,
    )

    class Meta:
        model = Student
        fields = [
            "id",
            "username",
            "email",
            "branch",
            "is_active",
            "email_verified_at",
            "created_at",
            "updated_at",
        ]


class LoginStudentSerializer(
    serializers.Serializer
):
    email = serializers.EmailField(
        write_only=True,
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        email = attrs["email"]
        password = attrs["password"]

        try:
            student = (
                Student.objects
                .select_related("branch")
                .get(
                    email__iexact=email,
                )
            )

        except Student.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "email": (
                        "Adresse email ou mot de passe incorrect."
                    )
                }
            )

        if not student.check_password(
            password
        ):
            raise serializers.ValidationError(
                {
                    "email": (
                        "Adresse email ou mot de passe incorrect."
                    )
                }
            )

        # if not student.is_active:
        #     raise serializers.ValidationError(
        #         {
        #             "email": (
        #                 "Votre adresse email n'est pas encore vérifiée."
        #             ),
        #             "code": "email_not_verified",
        #         }
        #     )

        attrs["student"] = student

        return attrs


class VerifyEmailSerializer(
    serializers.Serializer
):
    token = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )


class ResendVerificationEmailSerializer(
    serializers.Serializer
):
    email = serializers.EmailField(
        required=True,
    )

    def validate_email(self, value):
        return value.strip().lower()


class UpdateStudentNameSerializer(
    serializers.Serializer
):
    new_username = serializers.CharField(
        min_length=2,
        max_length=100,
        trim_whitespace=True,
    )

    confirm_username = serializers.CharField(
        min_length=2,
        max_length=100,
        trim_whitespace=True,
    )

    def validate_new_username(
        self,
        value,
    ):
        username = value.strip()

        if len(username) < 2:
            raise serializers.ValidationError(
                "Le nom doit contenir au moins 2 caractères."
            )

        return username

    def validate(self, attrs):
        new_username = attrs[
            "new_username"
        ].strip()

        confirm_username = attrs[
            "confirm_username"
        ].strip()

        if (
            new_username
            != confirm_username
        ):
            raise serializers.ValidationError(
                {
                    "confirm_username": (
                        "La confirmation du nom ne correspond pas."
                    )
                }
            )

        student = self.context[
            "request"
        ].user

        if (
            student.username.strip().lower()
            == new_username.lower()
        ):
            raise serializers.ValidationError(
                {
                    "new_username": (
                        "Le nouveau nom est identique au nom actuel."
                    )
                }
            )

        attrs["new_username"] = (
            new_username
        )

        return attrs

    def save(self, **kwargs):
        student = self.context[
            "request"
        ].user

        student.username = (
            self.validated_data[
                "new_username"
            ]
        )

        student.save(
            update_fields=[
                "username",
                "updated_at",
            ]
        )

        return student


class ChangeStudentPasswordSerializer(
    serializers.Serializer
):
    current_password = (
        serializers.CharField(
            write_only=True,
            min_length=8,
            trim_whitespace=False,
            style={
                "input_type": "password",
            },
        )
    )

    new_password = (
        serializers.CharField(
            write_only=True,
            min_length=8,
            trim_whitespace=False,
            style={
                "input_type": "password",
            },
        )
    )

    confirm_password = (
        serializers.CharField(
            write_only=True,
            min_length=8,
            trim_whitespace=False,
            style={
                "input_type": "password",
            },
        )
    )

    def validate_current_password(
        self,
        value,
    ):
        student = self.context[
            "request"
        ].user

        if not student.check_password(
            value
        ):
            raise serializers.ValidationError(
                "Le mot de passe actuel est incorrect."
            )

        return value

    def validate(self, attrs):
        current_password = attrs[
            "current_password"
        ]

        new_password = attrs[
            "new_password"
        ]

        confirm_password = attrs[
            "confirm_password"
        ]

        if (
            new_password
            != confirm_password
        ):
            raise serializers.ValidationError(
                {
                    "confirm_password": (
                        "La confirmation du mot de passe ne correspond pas."
                    )
                }
            )

        if (
            current_password
            == new_password
        ):
            raise serializers.ValidationError(
                {
                    "new_password": (
                        "Le nouveau mot de passe doit être différent de l'ancien."
                    )
                }
            )

        if new_password.isdigit():
            raise serializers.ValidationError(
                {
                    "new_password": (
                        "Le mot de passe ne doit pas contenir uniquement des chiffres."
                    )
                }
            )

        return attrs

    def save(self, **kwargs):
        student = self.context[
            "request"
        ].user

        student.set_password(
            self.validated_data[
                "new_password"
            ]
        )

        student.save(
            update_fields=[
                "password",
                "updated_at",
            ]
        )

        return student