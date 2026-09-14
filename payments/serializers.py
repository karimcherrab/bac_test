from rest_framework import serializers

from course.models import Chapter, Subject

from .access import has_pack_access, try_get_student
from .models import Pack, Purchase


class PackSerializer(serializers.ModelSerializer):
    """
    Serializer usable for BOTH:
      - frontend display
      - Swagger CRUD

    Swagger can write:
      chapter_id
      subject_id
    """

    chapter_id = serializers.PrimaryKeyRelatedField(
        source="chapter",
        queryset=Chapter.objects.all(),
        required=False,
        allow_null=True,
    )

    subject_id = serializers.PrimaryKeyRelatedField(
        source="subject",
        queryset=Subject.objects.all(),
        required=False,
        allow_null=True,
    )

    target_id = serializers.SerializerMethodField()
    target_title = serializers.SerializerMethodField()
    owned = serializers.SerializerMethodField()

    class Meta:
        model = Pack
        fields = [
            "id",
            "pack_type",
            "name",
            "description",
            "price_dzd",
            "chapter_id",
            "subject_id",
            "target_id",
            "target_title",
            "is_active",
            "metadata",
            "owned",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "target_id",
            "target_title",
            "owned",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = self.instance

        pack_type = attrs.get(
            "pack_type",
            getattr(instance, "pack_type", None),
        )

        chapter = attrs.get(
            "chapter",
            getattr(instance, "chapter", None),
        )

        subject = attrs.get(
            "subject",
            getattr(instance, "subject", None),
        )

        if pack_type == Pack.PackType.CHAPTER:
            if chapter is None:
                raise serializers.ValidationError({
                    "chapter_id": (
                        "chapter_id is required when "
                        "pack_type='chapter'."
                    )
                })

            if subject is not None:
                raise serializers.ValidationError({
                    "subject_id": (
                        "subject_id must be null when "
                        "pack_type='chapter'."
                    )
                })

        elif pack_type == Pack.PackType.SUBJECT:
            if subject is None:
                raise serializers.ValidationError({
                    "subject_id": (
                        "subject_id is required when "
                        "pack_type='subject'."
                    )
                })

            if chapter is not None:
                raise serializers.ValidationError({
                    "chapter_id": (
                        "chapter_id must be null when "
                        "pack_type='subject'."
                    )
                })

        else:
            raise serializers.ValidationError({
                "pack_type": "Use 'chapter' or 'subject'."
            })

        return attrs

    def create(self, validated_data):
        pack = Pack(**validated_data)

        # Applies model validation before INSERT.
        pack.full_clean()
        pack.save()

        return pack

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.full_clean()
        instance.save()

        return instance

    def get_target_id(self, obj):
        if obj.pack_type == Pack.PackType.SUBJECT:
            return obj.subject_id

        return obj.chapter_id

    def get_target_title(self, obj):
        return obj.target_title

    def get_owned(self, obj):
        request = self.context.get("request")

        if not request:
            return False

        student = try_get_student(request)

        if not student:
            return False

        return has_pack_access(student, obj)


class CreateCheckoutSerializer(serializers.Serializer):
    pack_id = serializers.IntegerField()

    payment_method = serializers.ChoiceField(
        choices=[
            "edahabia",
            "cib",
            "chargily_app",
        ],
        required=False,
        allow_null=True,
    )


class PurchaseSerializer(serializers.ModelSerializer):
    pack = PackSerializer(
        read_only=True,
    )

    class Meta:
        model = Purchase
        fields = [
            "id",
            "pack",
            "amount_dzd",
            "currency",
            "status",
            "checkout_url",
            "payment_method",
            "customer_email",
            "chargily_customer_id",
            "paid_at",
            "created_at",
        ]
