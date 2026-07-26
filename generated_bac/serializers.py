from rest_framework import serializers

from course.models import Branch, Chapter

from .models import GeneratedBacExercise


class GenerateBacExerciseRequestSerializer(serializers.Serializer):
    """
    التلميذ يرسل الوحدة والشعبة فقط.

    references_count اختياري، ويمكن عدم إرساله.
    selection_strategy اختياري، والوضع الافتراضي يختار
    تمارين عشوائية مع تنويع السنوات.
    """

    chapter_id = serializers.IntegerField(
        min_value=1,
    )

    branch_code = serializers.CharField(
        max_length=100,
    )

    references_count = serializers.IntegerField(
        min_value=1,
        max_value=3,
        default=1,
        required=False,
    )

    selection_strategy = serializers.ChoiceField(
        choices=[
            "diverse_random",
            "random",
            "latest_random",
        ],
        default="diverse_random",
        required=False,
    )

    def validate_chapter_id(self, value):
        if not Chapter.objects.filter(
            id=value,
        ).exists():
            raise serializers.ValidationError(
                "الوحدة غير موجودة."
            )

        return value

    def validate_branch_code(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "رمز الشعبة مطلوب."
            )

        if not Branch.objects.filter(
            code=value,
        ).exists():
            raise serializers.ValidationError(
                "الشعبة غير موجودة."
            )

        return value


class GenerateBacSolutionRequestSerializer(serializers.Serializer):
    regenerate = serializers.BooleanField(
        default=False,
        required=False,
    )


class GeneratedBacExerciseSerializer(serializers.ModelSerializer):
    chapter = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    has_solution = serializers.BooleanField(
        read_only=True,
    )

    class Meta:
        model = GeneratedBacExercise
        fields = [
            "id",
            "title",
            "exercise",
            "solution",
            "has_solution",
            "status",
            "selection_strategy",
            "chapter",
            "branch",
            "created_at",
            "updated_at",
        ]

    def get_chapter(self, obj):
        return {
            "id": obj.chapter_id,
            "code": getattr(
                obj.chapter,
                "code",
                "",
            ),
            "title": getattr(
                obj.chapter,
                "title",
                "",
            ),
        }

    def get_branch(self, obj):
        return {
            "id": obj.branch_id,
            "code": obj.branch.code,
            "name": obj.branch.name,
        }
