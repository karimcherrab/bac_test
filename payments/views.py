from django.db.models import Q

from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.viewsets import ModelViewSet

try:
    from drf_spectacular.utils import (
        OpenApiExample,
        OpenApiParameter,
        extend_schema,
        extend_schema_view,
    )
except ImportError:
    # The API still works without drf-spectacular.
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def extend_schema_view(**kwargs):
        def decorator(cls):
            return cls
        return decorator

    class OpenApiExample:
        def __init__(self, *args, **kwargs):
            pass

    class OpenApiParameter:
        QUERY = "query"

        def __init__(self, *args, **kwargs):
            pass

from .models import Pack
from .permissions import PackPermission
from .serializers import PackSerializer


CHAPTER_PACK_EXAMPLE = OpenApiExample(
    "Chapter pack",
    value={
        "pack_type": "chapter",
        "name": "الوحدة الأولى - المتابعة الزمنية",
        "description": "الوحدة كاملة مع الدروس والتمارين والبكالوريا",
        "price_dzd": 500,
        "chapter_id": 1,
        "subject_id": None,
        "is_active": True,
        "metadata": {},
    },
    request_only=True,
)

SUBJECT_PACK_EXAMPLE = OpenApiExample(
    "Subject pack",
    value={
        "pack_type": "subject",
        "name": "الفيزياء كاملة",
        "description": "جميع وحدات مادة الفيزياء",
        "price_dzd": 2500,
        "chapter_id": None,
        "subject_id": 1,
        "is_active": True,
        "metadata": {},
    },
    request_only=True,
)


@extend_schema_view(
    list=extend_schema(
        summary="List payment packs",
        description=(
            "Used by Backey frontend. "
            "Can be filtered with type, subject and chapter."
        ),
        parameters=[
            OpenApiParameter(
                name="type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="chapter or subject",
            ),
            OpenApiParameter(
                name="subject",
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="chapter",
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get one pack",
    ),
    create=extend_schema(
        summary="Create a pack (admin)",
        description=(
            "Requires an authenticated Django user "
            "with is_staff=True or is_superuser=True."
        ),
        examples=[
            CHAPTER_PACK_EXAMPLE,
            SUBJECT_PACK_EXAMPLE,
        ],
    ),
    update=extend_schema(
        summary="Replace a pack (admin)",
    ),
    partial_update=extend_schema(
        summary="Edit a pack (admin)",
    ),
    destroy=extend_schema(
        summary="Delete a pack (admin)",
    ),
)
class PackViewSet(ModelViewSet):
    serializer_class = PackSerializer
    # permission_classes = [PackPermission]

    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "name",
        "description",
        "chapter__title",
        "subject__name",
    ]

    ordering_fields = [
        "id",
        "price_dzd",
        "created_at",
        "updated_at",
    ]

    ordering = [
        "pack_type",
        "price_dzd",
        "id",
    ]

    def get_queryset(self):
        queryset = (
            Pack.objects
            .select_related(
                "chapter",
                "chapter__subject",
                "subject",
            )
            .all()
        )

        pack_type = self.request.query_params.get("type")
        subject_id = self.request.query_params.get("subject")
        chapter_id = self.request.query_params.get("chapter")

        if pack_type in {
            Pack.PackType.CHAPTER,
            Pack.PackType.SUBJECT,
        }:
            queryset = queryset.filter(
                pack_type=pack_type,
            )

        if subject_id:
            queryset = queryset.filter(
                Q(subject_id=subject_id)
                |
                Q(chapter__subject_id=subject_id)
            )

        if chapter_id:
            queryset = queryset.filter(
                chapter_id=chapter_id,
            )

        # Frontend normally only needs active offers.
        # Admin can pass ?include_inactive=1 from Swagger.
        include_inactive = (
            self.request.query_params.get(
                "include_inactive"
            )
        )

        if include_inactive not in {
            "1",
            "true",
            "True",
        }:
            queryset = queryset.filter(
                is_active=True,
            )

        return queryset
