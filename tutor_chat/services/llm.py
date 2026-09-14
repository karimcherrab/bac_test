import os

import requests
from django.conf import settings


class AnswerGenerationError(RuntimeError):
    pass


class TutorLLMClient:
    def __init__(self):
        self.api_key  = (
                os.getenv("GROQ_API_KEY")
                or os.getenv("API_KEY")
        )
        if not self.api_key :
            raise RuntimeError(
                "GROQ_API_KEY غير موجود."
            )
        self.api_url = getattr(
            settings,
            "TUTOR_CHAT_API_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.model = getattr(
            settings,
            "TUTOR_CHAT_MODEL",
            "openai/gpt-oss-120b",
        )
        self.timeout = int(getattr(settings, "TUTOR_CHAT_TIMEOUT", 75))

    def generate(self, messages):
        if not self.api_key:
            raise AnswerGenerationError(
                "TUTOR_CHAT_API_KEY/GROQ_API_KEY غير مضبوط في الخادم."
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.35,
            "top_p": 0.9,
            "max_tokens": 1800,
        }

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AnswerGenerationError(str(exc)) from exc

        if response.status_code >= 400:
            body = response.text[:1200]
            raise AnswerGenerationError(
                f"LLM HTTP {response.status_code}: {body}"
            )

        try:
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AnswerGenerationError(
                "صيغة استجابة النموذج غير متوقعة."
            ) from exc

        if not answer:
            raise AnswerGenerationError("النموذج أعاد إجابة فارغة.")

        return answer, self.model
