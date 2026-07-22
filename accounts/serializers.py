from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from course.models import Branch

from .models import Student


class StudentBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "id",
            "code",
            "name",
        ]


class StudentSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
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
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_username(self, value):
        username = value.strip()

        if len(username) < 2:
            raise serializers.ValidationError(
                "Le nom doit contenir au moins 2 caractères."
            )

        return username

    def validate_email(self, value):
        email = value.strip().lower()

        if Student.objects.filter(
            email__iexact=email,
        ).exists():
            raise serializers.ValidationError(
                "Email already exists"
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

        student = Student.objects.create(
            password=make_password(password),
            **validated_data,
        )

        return student


class StudentResponseSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]


class LoginStudentSerializer(serializers.Serializer):
    email = serializers.EmailField(
        write_only=True,
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    def validate_email(self, value):
        return value.strip().lower()