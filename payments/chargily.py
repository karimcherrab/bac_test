import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ChargilyAPIError(Exception):
    def __init__(self, message, *, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ChargilyClient:
    def __init__(self):
        self.base_url = settings.CHARGILY_BASE_URL.rstrip("/")
        self.secret_key = settings.CHARGILY_SECRET_KEY.strip()
        self.timeout = getattr(settings, "CHARGILY_TIMEOUT", 20)

    @property
    def headers(self):
        if not self.secret_key:
            raise ChargilyAPIError("CHARGILY_SECRET_KEY is missing.")
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.Timeout as exc:
            raise ChargilyAPIError("Chargily request timeout.") from exc
        except requests.RequestException as exc:
            raise ChargilyAPIError(f"Chargily connection error: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        if not response.ok:
            logger.error(
                "Chargily HTTP %s on %s: %s",
                response.status_code,
                endpoint,
                data,
            )
            raise ChargilyAPIError(
                f"Chargily HTTP {response.status_code}",
                status_code=response.status_code,
                response_data=data,
            )

        return data

    def create_customer(self, *, name, email):
        return self._request(
            "POST",
            "/customers",
            json={
                "name": str(name).strip(),
                "email": str(email).strip().lower(),
            },
        )

    def retrieve_customer(self, customer_id):
        return self._request(
            "GET",
            f"/customers/{customer_id}",
        )

    def create_checkout(
        self,
        *,
        amount,
        success_url,
        failure_url,
        webhook_endpoint,
        customer_id,
        payment_method=None,
        description="",
    ):
        payload = {
            "amount": int(amount),
            "currency": "dzd",
            "success_url": success_url,
            "failure_url": failure_url,
            "webhook_endpoint": webhook_endpoint,
            "customer_id": customer_id,
            "locale": "ar",
            "description": description,
            "collect_shipping_address": False,
            "chargily_pay_fees_allocation": settings.CHARGILY_FEES_ALLOCATION,
        }
        if payment_method:
            payload["payment_method"] = payment_method

        return self._request("POST", "/checkouts", json=payload)

    def retrieve_checkout(self, checkout_id):
        return self._request(
            "GET",
            f"/checkouts/{checkout_id}",
        )
