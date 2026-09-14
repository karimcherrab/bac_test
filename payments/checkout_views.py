import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import (
    DatabaseError,
    IntegrityError,
)
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import (
    get_current_student,
    has_pack_access,
)
from .chargily import (
    ChargilyAPIError,
    ChargilyClient,
)
from .customer_service import (
    ensure_chargily_customer,
)
from .models import (
    Pack,
    Purchase,
)
from .payment_service import (
    PaymentValidationError,
    mark_purchase_failed,
    mark_purchase_paid,
)
from .serializers import (
    CreateCheckoutSerializer,
    PurchaseSerializer,
)


logger = logging.getLogger(__name__)


def _debug_error_payload(
    detail,
    exc,
):
    payload = {
        "detail": detail,
    }

    if settings.DEBUG:
        payload[
            "server_error"
        ] = str(exc)

        if isinstance(
            exc,
            ChargilyAPIError,
        ):
            payload[
                "chargily_status"
            ] = exc.status_code

            payload[
                "chargily_error"
            ] = exc.response_data

    return payload


class CreateCheckoutView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
    ):
        student = get_current_student(
            request
        )

        serializer = (
            CreateCheckoutSerializer(
                data=request.data,
            )
        )

        serializer.is_valid(
            raise_exception=True,
        )

        pack_id = (
            serializer
            .validated_data[
                "pack_id"
            ]
        )

        payment_method = (
            serializer
            .validated_data
            .get(
                "payment_method"
            )
        )

        pack = get_object_or_404(
            Pack.objects.select_related(
                "subject",
                "chapter",
                "chapter__subject",
            ),
            id=pack_id,
            is_active=True,
        )

        if has_pack_access(
            student,
            pack,
        ):
            return Response(
                {
                    "detail": (
                        "أنت تملك هذا المحتوى بالفعل."
                    ),
                    "owned": True,
                },
                status=(
                    status
                    .HTTP_409_CONFLICT
                ),
            )

        pending = (
            Purchase.objects
            .filter(
                student=student,
                pack=pack,
                status=(
                    Purchase
                    .Status
                    .PENDING
                ),
            )
            .order_by(
                "-created_at"
            )
            .first()
        )

        if (
            pending
            and
            pending.checkout_url
        ):
            return Response(
                PurchaseSerializer(
                    pending,
                    context={
                        "request": request,
                    },
                ).data,
                status=(
                    status
                    .HTTP_200_OK
                ),
            )

        if pending:
            return Response(
                {
                    "detail": (
                        "عملية الدفع قيد الإنشاء."
                    )
                },
                status=(
                    status
                    .HTTP_409_CONFLICT
                ),
            )

        try:
            purchase = (
                Purchase.objects.create(
                    student=student,
                    pack=pack,
                    amount_dzd=(
                        pack.price_dzd
                    ),
                    currency="dzd",
                    status=(
                        Purchase
                        .Status
                        .PENDING
                    ),

                    # Important:
                    # comes from logged-in Student,
                    # never from React.
                    customer_email=(
                        student.email
                    ),
                )
            )

        except IntegrityError:
            pending = (
                Purchase.objects
                .filter(
                    student=student,
                    pack=pack,
                    status=(
                        Purchase
                        .Status
                        .PENDING
                    ),
                )
                .first()
            )

            if pending:
                return Response(
                    PurchaseSerializer(
                        pending,
                        context={
                            "request": request,
                        },
                    ).data,
                    status=200,
                )

            raise

        try:
            customer_id = (
                ensure_chargily_customer(
                    student
                )
            )

            purchase.chargily_customer_id = (
                customer_id
            )

            purchase.save(
                update_fields=[
                    "chargily_customer_id",
                    "updated_at",
                ]
            )

            frontend_url = (
                settings
                .FRONTEND_URL
                .rstrip("/")
            )

            backend_url = (
                settings
                .BACKEND_PUBLIC_URL
                .rstrip("/")
            )

            success_url = (
                f"{frontend_url}"
                f"/payment/success"
                f"?purchase={purchase.id}"
            )

            failure_url = (
                f"{frontend_url}"
                f"/payment/failed"
                f"?purchase={purchase.id}"
            )

            webhook_path = reverse(
                "payments:chargily-webhook"
            )

            webhook_endpoint = (
                f"{backend_url}"
                f"{webhook_path}"
            )

            client = ChargilyClient()

            checkout = (
                client.create_checkout(
                    amount=(
                        purchase
                        .amount_dzd
                    ),
                    success_url=(
                        success_url
                    ),
                    failure_url=(
                        failure_url
                    ),
                    webhook_endpoint=(
                        webhook_endpoint
                    ),
                    customer_id=(
                        customer_id
                    ),
                    payment_method=(
                        payment_method
                    ),
                    description=(
                        f"Backey - "
                        f"{pack.name}"
                    ),
                )
            )

        except (
            ChargilyAPIError,
            ValueError,
        ) as exc:
            logger.exception(
                "Chargily checkout "
                "creation failed."
            )

            purchase.status = (
                Purchase.Status.ERROR
            )

            purchase.provider_error = (
                str(exc)
            )

            if (
                isinstance(
                    exc,
                    ChargilyAPIError,
                )
                and exc.response_data
            ):
                purchase.provider_data = (
                    exc.response_data
                )

            purchase.save(
                update_fields=[
                    "status",
                    "provider_error",
                    "provider_data",
                    "updated_at",
                ]
            )

            return Response(
                _debug_error_payload(
                    "تعذر إنشاء عملية الدفع.",
                    exc,
                ),
                status=(
                    status
                    .HTTP_502_BAD_GATEWAY
                ),
            )

        checkout_id = str(
            checkout.get(
                "id"
            )
            or ""
        ).strip()

        checkout_url = str(
            checkout.get(
                "checkout_url"
            )
            or checkout.get(
                "url"
            )
            or ""
        ).strip()

        if (
            not checkout_id
            or not checkout_url
        ):
            purchase.status = (
                Purchase.Status.ERROR
            )
            purchase.provider_data = (
                checkout
            )
            purchase.provider_error = (
                "Chargily response missing "
                "checkout id/url."
            )
            purchase.save()

            return Response(
                {
                    "detail": (
                        "Chargily returned "
                        "an invalid checkout."
                    )
                },
                status=502,
            )

        purchase.chargily_checkout_id = (
            checkout_id
        )
        purchase.checkout_url = (
            checkout_url
        )
        purchase.provider_data = (
            checkout
        )
        purchase.provider_error = ""

        purchase.save(
            update_fields=[
                "chargily_checkout_id",
                "checkout_url",
                "provider_data",
                "provider_error",
                "updated_at",
            ]
        )

        return Response(
            PurchaseSerializer(
                purchase,
                context={
                    "request": request,
                },
            ).data,
            status=(
                status.HTTP_201_CREATED
            ),
        )


class MyPurchasesView(
    ListAPIView
):
    permission_classes = [
        IsAuthenticated,
    ]
    serializer_class = (
        PurchaseSerializer
    )

    def get_queryset(self):
        student = (
            get_current_student(
                self.request
            )
        )

        return (
            Purchase.objects
            .filter(
                student=student,
            )
            .select_related(
                "pack",
                "pack__chapter",
                "pack__chapter__subject",
                "pack__subject",
            )
        )


class PurchaseDetailView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        purchase_id,
    ):
        student = (
            get_current_student(
                request
            )
        )

        purchase = (
            get_object_or_404(
                Purchase.objects
                .select_related(
                    "pack",
                    "pack__chapter",
                    "pack__subject",
                ),
                id=purchase_id,
                student=student,
            )
        )

        return Response(
            PurchaseSerializer(
                purchase,
                context={
                    "request": request,
                },
            ).data
        )


class RefreshPurchaseView(
    APIView
):
    """
    Fallback after return from Chargily.

    If webhook is delayed or failed,
    this endpoint repairs local status
    AND StudentAccess from Chargily.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        purchase_id,
    ):
        student = (
            get_current_student(
                request
            )
        )

        purchase = (
            get_object_or_404(
                Purchase.objects
                .select_related(
                    "pack",
                    "pack__chapter",
                    "pack__subject",
                ),
                id=purchase_id,
                student=student,
            )
        )

        if (
            not purchase
            .chargily_checkout_id
        ):
            return Response(
                {
                    "detail": (
                        "Checkout ID missing."
                    )
                },
                status=400,
            )

        client = ChargilyClient()

        try:
            checkout = (
                client.retrieve_checkout(
                    purchase
                    .chargily_checkout_id
                )
            )

            provider_status = str(
                checkout.get(
                    "status",
                    "",
                )
            ).lower()

            if (
                provider_status
                == "paid"
            ):
                purchase = (
                    mark_purchase_paid(
                        purchase.id,
                        checkout,
                    )
                )

            elif provider_status in {
                "failed",
                "cancelled",
                "canceled",
                "expired",
            }:
                purchase = (
                    mark_purchase_failed(
                        purchase.id,
                        checkout,
                    )
                )

            else:
                purchase.provider_data = (
                    checkout
                )
                purchase.save(
                    update_fields=[
                        "provider_data",
                        "updated_at",
                    ]
                )

        except ChargilyAPIError as exc:
            logger.exception(
                "Chargily refresh failed."
            )

            return Response(
                _debug_error_payload(
                    "تعذر التحقق من الدفع.",
                    exc,
                ),
                status=502,
            )

        except (
            PaymentValidationError
        ) as exc:
            logger.exception(
                "Payment validation failed."
            )

            purchase.provider_error = (
                str(exc)
            )
            purchase.save(
                update_fields=[
                    "provider_error",
                    "updated_at",
                ]
            )

            return Response(
                _debug_error_payload(
                    (
                        "بيانات الدفع لا "
                        "تتطابق مع الطلب."
                    ),
                    exc,
                ),
                status=409,
            )

        except DatabaseError as exc:
            logger.exception(
                "Database error while "
                "granting paid access."
            )

            return Response(
                _debug_error_payload(
                    (
                        "تم تأكيد الدفع، لكن "
                        "تعذر حفظ صلاحية الوصول."
                    ),
                    exc,
                ),
                status=500,
            )

        except Exception as exc:
            logger.exception(
                "Unexpected purchase "
                "refresh error."
            )

            return Response(
                _debug_error_payload(
                    (
                        "لم نستطع تأكيد "
                        "العملية الآن."
                    ),
                    exc,
                ),
                status=500,
            )

        purchase.refresh_from_db()

        return Response(
            PurchaseSerializer(
                purchase,
                context={
                    "request": request,
                },
            ).data
        )


@csrf_exempt
@require_POST
def chargily_webhook(
    request,
):
    signature = (
        request.headers.get(
            "signature"
        )
    )

    if not signature:
        return JsonResponse(
            {
                "detail": (
                    "Missing signature."
                )
            },
            status=400,
        )

    secret_key = (
        settings
        .CHARGILY_SECRET_KEY
        .strip()
    )

    raw_body = request.body

    computed_signature = (
        hmac.new(
            secret_key.encode(
                "utf-8"
            ),
            raw_body,
            hashlib.sha256,
        )
        .hexdigest()
    )

    if not hmac.compare_digest(
        signature,
        computed_signature,
    ):
        logger.warning(
            "Invalid Chargily "
            "webhook signature."
        )

        return JsonResponse(
            {
                "detail": (
                    "Invalid signature."
                )
            },
            status=403,
        )

    try:
        event = json.loads(
            raw_body.decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return JsonResponse(
            {
                "detail": (
                    "Invalid JSON."
                )
            },
            status=400,
        )

    event_type = str(
        event.get(
            "type"
        )
        or ""
    )

    checkout = (
        event.get(
            "data"
        )
        or {}
    )

    checkout_id = str(
        checkout.get(
            "id"
        )
        or ""
    ).strip()

    if not checkout_id:
        return JsonResponse(
            {
                "received": True,
            },
            status=200,
        )

    purchase = (
        Purchase.objects
        .filter(
            chargily_checkout_id=(
                checkout_id
            )
        )
        .first()
    )

    # Compatibility with old checkouts
    # where you sent purchase_id metadata.
    if not purchase:
        metadata = (
            checkout.get(
                "metadata"
            )
            or {}
        )

        if isinstance(
            metadata,
            dict,
        ):
            local_purchase_id = (
                metadata.get(
                    "purchase_id"
                )
            )

            if local_purchase_id:
                purchase = (
                    Purchase.objects
                    .filter(
                        id=(
                            local_purchase_id
                        )
                    )
                    .first()
                )

    if not purchase:
        logger.warning(
            "Chargily checkout "
            "not found locally: %s",
            checkout_id,
        )

        return JsonResponse(
            {
                "received": True,
            },
            status=200,
        )

    try:
        if (
            event_type
            == "checkout.paid"
        ):
            mark_purchase_paid(
                purchase.id,
                checkout,
                webhook_data=event,
            )

        elif event_type in {
            "checkout.failed",
            "checkout.canceled",
            "checkout.cancelled",
            "checkout.expired",
        }:
            mark_purchase_failed(
                purchase.id,
                checkout,
                webhook_data=event,
            )

    except Exception as exc:
        logger.exception(
            "Chargily webhook "
            "processing failed."
        )

        response_data = {
            "detail": (
                "Webhook processing error."
            )
        }

        if settings.DEBUG:
            response_data[
                "server_error"
            ] = str(exc)

        return JsonResponse(
            response_data,
            status=500,
        )

    return JsonResponse(
        {
            "received": True,
        },
        status=200,
    )
