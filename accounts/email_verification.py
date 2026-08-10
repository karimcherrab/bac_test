from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


EMAIL_VERIFICATION_SALT = (
    "student.email.verification"
)


class InvalidVerificationToken(Exception):
    pass


class ExpiredVerificationToken(Exception):
    pass


def generate_email_verification_token(
    student,
) -> str:
    """
    ينشئ Token موقّعًا يحتوي على:
    - student_id
    - email

    لا يحتوي على كلمة المرور.
    """

    payload = {
        "student_id": student.pk,
        "email": student.email,
    }

    return signing.dumps(
        payload,
        salt=EMAIL_VERIFICATION_SALT,
        compress=True,
    )


def decode_email_verification_token(
    token: str,
) -> dict:
    """
    يتحقق من:
    - صحة التوقيع
    - مدة صلاحية الرابط
    """

    max_age = getattr(
        settings,
        "EMAIL_VERIFICATION_MAX_AGE",
        86400,
    )

    try:
        return signing.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=max_age,
        )

    except signing.SignatureExpired as exc:
        raise ExpiredVerificationToken(
            "Le lien de vérification a expiré."
        ) from exc

    except signing.BadSignature as exc:
        raise InvalidVerificationToken(
            "Le lien de vérification est invalide."
        ) from exc


def build_verification_url(
    student,
) -> str:
    token = generate_email_verification_token(
        student
    )

    frontend_url = getattr(
        settings,
        "FRONTEND_URL",
        "http://localhost:5173",
    ).rstrip("/")

    query_string = urlencode(
        {
            "token": token,
        }
    )

    return (
        f"{frontend_url}/verify-email?"
        f"{query_string}"
    )


def send_student_verification_email(
    student,
) -> None:
    verification_url = build_verification_url(
        student
    )

    context = {
        "student": student,
        "verification_url": verification_url,
        "expiration_hours": 24,
    }

    subject = (
        "Confirmez votre adresse email "
        "- Bac Academy"
    )

    text_content = render_to_string(
        "emails/student_verification.txt",
        context,
    )

    html_content = render_to_string(
        "emails/student_verification.html",
        context,
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[student.email],
    )

    message.attach_alternative(
        html_content,
        "text/html",
    )

    # سيُظهر Exception عند فشل الإرسال
    message.send(
        fail_silently=False,
    )