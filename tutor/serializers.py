from rest_framework import serializers

from tutor.models import (
    TutorChatSession,
    TutorChatMessage,
)


class TutorChatMessageSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = TutorChatMessage

        fields = [
            "id",
            "role",
            "content",
            "sources",
            "metadata",
            "created_at",
        ]

        read_only_fields = fields


class TutorChatSessionSerializer(
    serializers.ModelSerializer
):
    messages_count = serializers.IntegerField(
        source="messages.count",
        read_only=True,
    )

    class Meta:
        model = TutorChatSession

        fields = [
            "id",
            "title",
            "chapter",
            "axis",
            "is_active",
            "messages_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "messages_count",
        ]


class TutorChatSessionDetailSerializer(
    serializers.ModelSerializer
):
    messages = TutorChatMessageSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = TutorChatSession

        fields = [
            "id",
            "title",
            "chapter",
            "axis",
            "is_active",
            "messages",
            "created_at",
            "updated_at",
        ]


class TutorChatRequestSerializer(
    serializers.Serializer
):
    question = serializers.CharField(
        max_length=4000,
        trim_whitespace=True,
    )

    session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    chapter_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    axis_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )