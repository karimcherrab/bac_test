from django.contrib import admin

from .models import StudentMessage, StudentSession


@admin.register(StudentSession)
class StudentSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student",
        "chapter",
        "current_axis",
        "current_section",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "chapter")
    search_fields = (
        "student__id",
        "chapter__title",
        "current_exercise_title",
        "last_question",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(StudentMessage)
class StudentMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "role",
        "chapter",
        "axis",
        "created_at",
    )
    list_filter = ("role", "chapter", "axis")
    search_fields = ("content",)
    readonly_fields = ("created_at",)
