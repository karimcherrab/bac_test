from django.db import models


# class Student(models.Model):
#     BRANCH_CHOICES = [
#         ("math", "Mathématiques"),
#         ("science", "Sciences expérimentales"),
#         ("math_tech", "Mathématiques techniques"),
#     ]
#
#     username = models.CharField(max_length=100)
#     email = models.EmailField(unique=True)
#     password = models.CharField(max_length=128)
#     branch = models.CharField(max_length=20, choices=BRANCH_CHOICES)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     @property
#     def is_authenticated(self):
#         return True
#
#     class Meta:
#         db_table = "students"
#         ordering = ["username"]
#
#     def __str__(self):
#         return self.username
#



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
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
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