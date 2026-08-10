from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from groq import Groq

from .exceptions import AIResponseError

logger = logging.getLogger(__name__)


class GroqJSONClient:
    """
    عميل Groq موحد لإرجاع JSON.

    المحاولة الأولى:
    - JSON mode.

    المحاولة الثانية عند فشل JSON أو parsing:
    - دون JSON mode.
    - مع تعليمة واضحة لإعادة JSON صالح من البداية.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"
    DEFAULT_MAX_TOKENS = 5500
    MAX_FALLBACK_TOKENS = 8000

    def __init__(self, model: str | None = None):
        api_key = os.getenv("API_KEY") or os.getenv("GROQ_API_KEY")

        if not api_key:
            raise AIResponseError(
                "API_KEY أو GROQ_API_KEY غير موجود في متغيرات البيئة."
            )

        self.client = Groq(api_key=api_key)
        self.model = (
            model
            or os.getenv("GROQ_EXERCISE_MODEL")
            or os.getenv("GROQ_MODEL")
            or self.DEFAULT_MODEL
        )

    @staticmethod
    def estimate_tokens(value: str) -> int:
        """تقدير تقريبي محافظ للنص العربي."""
        return max(1, len(value or "") // 3)

    @staticmethod
    def is_json_mode_error(exc: Exception) -> bool:
        message = str(exc).lower()
        markers = (
            "json_validate_failed",
            "failed to generate json",
            "failed_generation",
            "invalid_request_error",
            "json",
        )
        return any(marker in message for marker in markers)

    @staticmethod
    def is_token_error(exc: Exception) -> bool:
        message = str(exc).lower()
        markers = (
            "413",
            "request too large",
            "tokens per minute",
            "rate_limit_exceeded",
            "context_length",
            "maximum context",
            "too many tokens",
        )
        return any(marker in message for marker in markers)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> tuple[dict[str, Any], str]:
        output_limit = int(
            max_tokens or self.DEFAULT_MAX_TOKENS
        )

        logger.info(
            "Groq request model=%s chars=%s estimated_tokens=%s max_tokens=%s",
            self.model,
            len(user_prompt or ""),
            self.estimate_tokens(user_prompt),
            output_limit,
        )

        try:
            parsed = self._request(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=output_limit,
                json_mode=True,
            )
            return parsed, self.model

        except Exception as first_exc:
            logger.warning(
                "Groq JSON mode failed: %s",
                first_exc,
            )

            can_retry = (
                self.is_json_mode_error(first_exc)
                or self.is_token_error(first_exc)
                or isinstance(first_exc, AIResponseError)
            )

            if not can_retry:
                raise AIResponseError(
                    "فشل الاتصال بنموذج Groq: "
                    f"{first_exc}"
                ) from first_exc

            retry_prompt = self._build_retry_prompt(
                prompt=user_prompt,
                error=str(first_exc),
            )

            fallback_tokens = min(
                max(output_limit, 4400),
                self.MAX_FALLBACK_TOKENS,
            )

            try:
                parsed = self._request(
                    system_prompt=system_prompt,
                    user_prompt=retry_prompt,
                    temperature=min(temperature, 0.08),
                    max_tokens=fallback_tokens,
                    json_mode=False,
                )
                return parsed, self.model

            except Exception as retry_exc:
                logger.exception(
                    "Groq fallback generation failed"
                )
                raise AIResponseError(
                    "فشل توليد JSON بعد إعادة المحاولة: "
                    f"{retry_exc}"
                ) from retry_exc

    def _request(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
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
        }

        if json_mode:
            kwargs["response_format"] = {
                "type": "json_object",
            }

        try:
            completion = self.client.chat.completions.create(
                **kwargs
            )
        except Exception as exc:
            raise AIResponseError(
                f"خطأ من Groq: {exc}"
            ) from exc

        try:
            content = completion.choices[0].message.content
        except (
            AttributeError,
            IndexError,
            TypeError,
        ) as exc:
            raise AIResponseError(
                "استجابة Groq غير مكتملة."
            ) from exc

        logger.info(
            "Groq response chars=%s json_mode=%s",
            len(content or ""),
            json_mode,
        )

        return self._parse_json(content)

    @staticmethod
    def _build_retry_prompt(
        *,
        prompt: str,
        error: str,
    ) -> str:
        short_error = str(error or "")[:400]

        return f"""
{prompt}

تعليمة تصحيح أخيرة:
فشلت المحاولة السابقة لأن JSON كان غير صالح أو غير مكتمل.

الخطأ المختصر:
{short_error}

أعد إنشاء JSON كاملًا من البداية.

قواعد إلزامية للإخراج:
- لا تضع أي نص قبل JSON أو بعده.
- لا تستعمل Markdown أو ```.
- استعمل $...$ للصيغ الرياضية عند الحاجة.
- لا تستعمل \\( أو \\) أو \\[ أو \\].
- أغلق كل علامات الاقتباس.
- أغلق كل قائمة وكل كائن JSON.
- لا تكرر نفس الشرح دون حاجة.
- اجعل النصوص والخطوات مختصرة وواضحة.
""".strip()

    @staticmethod
    def _remove_code_fences(value: str) -> str:
        cleaned = str(value or "").strip()

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        return cleaned.strip()

    @classmethod
    def _parse_json(cls, value: str) -> dict[str, Any]:
        if not value:
            raise AIResponseError(
                "إجابة النموذج فارغة."
            )

        cleaned = cls._remove_code_fences(value)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")

            if start < 0 or end <= start:
                raise AIResponseError(
                    "النموذج لم يرجع JSON صالحًا."
                )

            candidate = cleaned[start:end + 1]

            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError as exc:
                logger.error(
                    "Invalid Groq JSON preview: %s",
                    candidate[:2000],
                )
                raise AIResponseError(
                    "JSON الناتج غير مكتمل أو غير صالح: "
                    f"{exc}"
                ) from exc

        if not isinstance(parsed, dict):
            raise AIResponseError(
                "إجابة النموذج يجب أن تكون JSON object."
            )

        return parsed
