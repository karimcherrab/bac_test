import logging

from django.conf import settings
from django.db import transaction

from .chargily import ChargilyAPIError, ChargilyClient
from .models import ChargilyCustomerLink


logger = logging.getLogger(__name__)


def _environment():
    mode = str(
        getattr(settings, "CHARGILY_MODE", "test")
    ).lower()

    if mode == "live":
        return ChargilyCustomerLink.Environment.LIVE

    return ChargilyCustomerLink.Environment.TEST


def _student_name(student):
    username = str(
        getattr(student, "username", "") or ""
    ).strip()

    if username:
        return username

    email = str(
        getattr(student, "email", "") or ""
    ).strip()

    if "@" in email:
        return email.split("@", 1)[0]

    return "Backey Student"


@transaction.atomic
def ensure_chargily_customer(student):
    """
    Uses ONLY the authenticated Student data.
    The frontend cannot choose another email.
    """

    email = str(
        getattr(student, "email", "") or ""
    ).strip().lower()

    if not email:
        raise ValueError(
            "The logged-in student has no email."
        )

    name = _student_name(student)
    environment = _environment()

    link = (
        ChargilyCustomerLink.objects
        .select_for_update()
        .filter(
            student=student,
            environment=environment,
        )
        .first()
    )

    client = ChargilyClient()

    if (
        link
        and link.email_snapshot.lower() == email
    ):
        try:
            customer = client.retrieve_customer(
                link.customer_id
            )

            remote_email = str(
                customer.get("email") or ""
            ).strip().lower()

            if (
                not remote_email
                or remote_email == email
            ):
                return link.customer_id

        except ChargilyAPIError as exc:
            if exc.status_code not in {
                404,
                410,
            }:
                raise

    customer = client.create_customer(
        name=name,
        email=email,
    )

    customer_id = str(
        customer.get("id") or ""
    ).strip()

    if not customer_id:
        raise ChargilyAPIError(
            "Chargily customer response has no id.",
            response_data=customer,
        )

    if link:
        link.customer_id = customer_id
        link.email_snapshot = email
        link.name_snapshot = name
        link.save(
            update_fields=[
                "customer_id",
                "email_snapshot",
                "name_snapshot",
                "updated_at",
            ]
        )
    else:
        ChargilyCustomerLink.objects.create(
            student=student,
            environment=environment,
            customer_id=customer_id,
            email_snapshot=email,
            name_snapshot=name,
        )

    return customer_id
