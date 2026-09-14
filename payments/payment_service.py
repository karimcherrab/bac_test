import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import (
    Pack,
    Purchase,
    StudentAccess,
)


logger = logging.getLogger(__name__)


class PaymentValidationError(Exception):
    pass


def _amount_as_decimal(value):
    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        raise PaymentValidationError(
            "Invalid checkout amount."
        )


def validate_checkout(
    purchase,
    checkout,
):
    checkout_id = str(
        checkout.get("id") or ""
    ).strip()

    if not checkout_id:
        raise PaymentValidationError(
            "Checkout ID is missing."
        )

    if (
        purchase.chargily_checkout_id
        and checkout_id
        != purchase.chargily_checkout_id
    ):
        raise PaymentValidationError(
            "Checkout ID mismatch."
        )

    remote_amount = _amount_as_decimal(
        checkout.get("amount")
    )

    local_amount = Decimal(
        str(purchase.amount_dzd)
    )

    if remote_amount != local_amount:
        raise PaymentValidationError(
            (
                "Checkout amount mismatch: "
                f"remote={remote_amount}, "
                f"local={local_amount}."
            )
        )

    currency = checkout.get(
        "currency"
    )

    if (
        currency is not None
        and str(currency).lower()
        != "dzd"
    ):
        raise PaymentValidationError(
            "Checkout currency mismatch."
        )


def grant_purchase_access(
    purchase,
):
    """
    Idempotent:
    can safely be called by webhook
    and by the refresh endpoint.
    """

    pack = purchase.pack

    if (
        pack.pack_type
        == Pack.PackType.SUBJECT
    ):
        if not pack.subject_id:
            raise PaymentValidationError(
                "Subject pack has no subject."
            )

        access, created = (
            StudentAccess.objects
            .get_or_create(
                student=purchase.student,
                subject=pack.subject,
                defaults={
                    "source_purchase": (
                        purchase
                    ),
                },
            )
        )

    elif (
        pack.pack_type
        == Pack.PackType.CHAPTER
    ):
        if not pack.chapter_id:
            raise PaymentValidationError(
                "Chapter pack has no chapter."
            )

        access, created = (
            StudentAccess.objects
            .get_or_create(
                student=purchase.student,
                chapter=pack.chapter,
                defaults={
                    "source_purchase": (
                        purchase
                    ),
                },
            )
        )

    else:
        raise PaymentValidationError(
            "Unsupported pack type."
        )

    if (
        not created
        and access.source_purchase_id
        is None
    ):
        access.source_purchase = (
            purchase
        )

        access.save(
            update_fields=[
                "source_purchase",
            ]
        )

    return access


@transaction.atomic
def mark_purchase_paid(
    purchase_id,
    checkout,
    webhook_data=None,
):
    """
    IMPORTANT:
    We lock ONLY the Purchase row.

    Do NOT combine select_for_update()
    with select_related("pack__chapter",
                        "pack__subject")
    because chapter/subject are nullable
    and PostgreSQL rejects FOR UPDATE
    on the nullable side of an OUTER JOIN.
    """

    purchase = (
        Purchase.objects
        .select_for_update()
        .get(
            id=purchase_id,
        )
    )

    validate_checkout(
        purchase,
        checkout,
    )

    # Accessing purchase.pack / purchase.student
    # performs normal related-object queries.
    # The Purchase row remains locked until
    # this transaction finishes.
    access = grant_purchase_access(
        purchase
    )

    purchase.status = (
        Purchase.Status.PAID
    )

    if purchase.paid_at is None:
        purchase.paid_at = (
            timezone.now()
        )

    payment_method = (
        checkout.get(
            "payment_method"
        )
    )

    if payment_method:
        purchase.payment_method = (
            str(payment_method)
        )

    purchase.provider_data = (
        checkout
    )

    purchase.provider_error = ""

    if webhook_data is not None:
        purchase.webhook_data = (
            webhook_data
        )

    purchase.save(
        update_fields=[
            "status",
            "paid_at",
            "payment_method",
            "provider_data",
            "webhook_data",
            "provider_error",
            "updated_at",
        ]
    )

    logger.info(
        (
            "Purchase %s paid; "
            "access %s granted."
        ),
        purchase.id,
        access.id,
    )

    return purchase


@transaction.atomic
def mark_purchase_failed(
    purchase_id,
    checkout=None,
    webhook_data=None,
):
    purchase = (
        Purchase.objects
        .select_for_update()
        .get(
            id=purchase_id,
        )
    )

    if (
        purchase.status
        == Purchase.Status.PAID
    ):
        return purchase

    purchase.status = (
        Purchase.Status.FAILED
    )

    if checkout:
        purchase.provider_data = (
            checkout
        )

    if webhook_data is not None:
        purchase.webhook_data = (
            webhook_data
        )

    purchase.save(
        update_fields=[
            "status",
            "provider_data",
            "webhook_data",
            "updated_at",
        ]
    )

    return purchase
