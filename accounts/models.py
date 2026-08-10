from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.db import models


class Branch(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(
        max_length=150,
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Student(models.Model):
    username = models.CharField(
        max_length=100,
        db_index=True,
    )

    email = models.EmailField(
        unique=True,
        db_index=True,
    )

    password = models.CharField(
        max_length=128,
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="students",
    )

    is_active = models.BooleanField(
        default=False,
        db_index=True,
    )

    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def set_password(self, raw_password):
        """
        تشفير كلمة المرور قبل حفظها.
        """
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """
        التحقق من كلمة المرور الحالية.
        """
        return check_password(
            raw_password,
            self.password,
        )

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    class Meta:
        db_table = "students"
        ordering = ["username"]
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return f"{self.username} - {self.email}"