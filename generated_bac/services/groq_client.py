import json
import os
from typing import Any

import requests
from django.conf import settings

from .exceptions import AIResponseError


class GroqJSONClient:
    endpoint = (
        "https://api.groq.com/openai/v1/"
        "chat/completions"
    )

    def __init__(self):
        self.api_key =   os.getenv(
            "API_KEY"
        )

        self.model =  "openai/gpt-oss-120b"

        self.timeout = 120

        if not self.api_key:
            raise AIResponseError(
                "GROQ_API_KEY غير موجود."
            )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[dict[str, Any], str]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "response_format": {
                "type": "json_object",
            },
        }

        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Authorization": (
                        f"Bearer {self.api_key}"
                    ),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AIResponseError(
                "تعذر الاتصال بخدمة الذكاء الاصطناعي."
            ) from exc

        if response.status_code >= 400:
            raise AIResponseError(
                "خطأ من Groq "
                f"({response.status_code}): "
                f"{response.text[:800]}"
            )

        try:
            body = response.json()
            raw_content = (
                body["choices"][0]
                ["message"]["content"]
            )
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise AIResponseError(
                "استجابة Groq غير مكتملة."
            ) from exc

        if isinstance(raw_content, dict):
            return raw_content, self.model

        try:
            return (
                json.loads(raw_content),
                self.model,
            )
        except json.JSONDecodeError as exc:
            raise AIResponseError(
                "Groq لم يُرجع JSON صالحًا."
            ) from exc
