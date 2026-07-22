from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from groq import Groq

from exercise_generation.services.exceptions import (
    ExerciseGenerationError,
    ExerciseParsingError,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedSingleExerciseResult:
    exercise: dict[str, Any]
    model: str
    raw_response: dict[str, Any]


class ExerciseAIGenerator:
    """
    مولد تمرين واحد.

    المحاولة الأولى:
    - JSON mode

    المحاولة الثانية:
    - دون JSON mode عند فشل json_validate_failed
    """

    DEFAULT_MAX_OUTPUT_TOKENS = 4200
    FALLBACK_MAX_OUTPUT_TOKENS = 4400

    def __init__(
        self,
        model: str | None = None,
    ):

        api_key = os.getenv(
            "API_KEY"
        )
        if not api_key:
            raise ExerciseGenerationError(
                "GROQ_API_KEY غير موجود في متغيرات البيئة."
            )

        self.client = Groq(
            api_key=api_key,
        )

        self.model = (
            model
            or os.getenv(
                "GROQ_EXERCISE_MODEL",
                "openai/gpt-oss-120b",
            )
        )

    @staticmethod
    def estimate_tokens(
        value: str,
    ) -> int:
        """
        تقدير تقريبي ومحافظ للنص العربي.
        """
        return max(
            1,
            len(value or "") // 3,
        )

    @staticmethod
    def is_json_mode_error(
        exc: Exception,
    ) -> bool:
        message = str(exc).lower()

        markers = (
            "json_validate_failed",
            "failed to generate json",
            "failed_generation",
            "invalid_request_error",
        )

        return any(
            marker in message
            for marker in markers
        )

    @staticmethod
    def is_token_error(
        exc: Exception,
    ) -> bool:
        message = str(exc).lower()

        markers = (
            "413",
            "request too large",
            "tokens per minute",
            "rate_limit_exceeded",
            "context_length",
            "maximum context",
        )

        return any(
            marker in message
            for marker in markers
        )

    def generate_one(
        self,
        *,
        prompt: str,
        max_output_tokens: int | None = None,
    ) -> GeneratedSingleExerciseResult:
        output_limit = int(
            max_output_tokens
            or self.DEFAULT_MAX_OUTPUT_TOKENS
        )

        input_estimate = self.estimate_tokens(
            prompt
        )

        logger.info(
            (
                "Exercise prompt chars=%s "
                "estimated_input_tokens=%s "
                "max_output_tokens=%s"
            ),
            len(prompt),
            input_estimate,
            output_limit,
        )

        system_prompt = self._system_prompt()

        try:
            return self._request(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=output_limit,
                json_mode=True,
            )

        except Exception as first_exc:
            logger.warning(
                "JSON mode generation failed: %s",
                first_exc,
            )

            can_retry = (
                self.is_json_mode_error(first_exc)
                or self.is_token_error(first_exc)
                or isinstance(
                    first_exc,
                    ExerciseParsingError,
                )
            )

            if not can_retry:
                raise ExerciseGenerationError(
                    "فشل الاتصال بنموذج التوليد: "
                    f"{first_exc}"
                ) from first_exc

            retry_prompt = self._build_retry_prompt(
                prompt=prompt,
                error=str(first_exc),
            )

            try:
                return self._request(
                    prompt=retry_prompt,
                    system_prompt=system_prompt,
                    max_tokens=(
                        self.FALLBACK_MAX_OUTPUT_TOKENS
                    ),
                    json_mode=False,
                )

            except Exception as retry_exc:
                logger.exception(
                    "Fallback generation failed"
                )

                if isinstance(
                    retry_exc,
                    ExerciseParsingError,
                ):
                    raise retry_exc

                raise ExerciseGenerationError(
                    "فشل الاتصال بنموذج التوليد "
                    "بعد إعادة المحاولة: "
                    f"{retry_exc}"
                ) from retry_exc

    def _request(
        self,
        *,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        json_mode: bool,
    ) -> GeneratedSingleExerciseResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.08,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }

        if json_mode:
            kwargs["response_format"] = {
                "type": "json_object",
            }

        completion = (
            self.client.chat.completions.create(
                **kwargs
            )
        )

        content = (
            completion
            .choices[0]
            .message
            .content
        )

        logger.info(
            "Generated response chars=%s json_mode=%s",
            len(content or ""),
            json_mode,
        )

        parsed = self._parse_json(
            content
        )

        exercise = parsed.get("exercise")

        if not isinstance(exercise, dict):
            raise ExerciseParsingError(
                "المفتاح exercise غير موجود "
                "أو ليس JSON object."
            )

        return GeneratedSingleExerciseResult(
            exercise=exercise,
            model=self.model,
            raw_response=parsed,
        )

    @staticmethod
    def _system_prompt() -> str:
        return """
أنت أستاذ رياضيات جزائري متخصص في البكالوريا.

أنشئ تمرينًا واحدًا فقط من المحور الذي يحدده المستخدم.

القواعد:
- لا تدخل أي مفهوم من محور آخر.
- اجعل التمرين قريبًا من أسلوب البكالوريا.
- اجعل الحسابات بسيطة وغير معقدة.
- حل جميع المطالب.
- اشرح كل انتقال مهم.
- لا تكرر نفس الشرح.
- استعمل $...$ للرياضيات.
- لا تستعمل Markdown.
- أعد JSON صالحًا فقط.
- أغلق جميع النصوص والأقواس والقوائم.
""".strip()

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

أعد إنشاء JSON من البداية ولا تحاول إكمال الإجابة السابقة.

لتجنب الخطأ:
- قلل طول الجمل.
- لا تستعمل \\[ أو \\].
- لا تستعمل \\( أو \\).
- استعمل $...$ للرياضيات.
- لا تكرر الشرطة المائلة.
- اجعل كل calculation قصيرًا.
- أغلق كل علامات الاقتباس.
- أغلق كل قائمة وكل كائن.
- لا تضع نصًا خارج JSON.
""".strip()

    @staticmethod
    def _remove_code_fences(
        value: str,
    ) -> str:
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
    def _parse_json(
        cls,
        value: str,
    ) -> dict[str, Any]:
        if not value:
            raise ExerciseParsingError(
                "إجابة النموذج فارغة."
            )

        cleaned = cls._remove_code_fences(
            value
        )

        try:
            parsed = json.loads(cleaned)

        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")

            if start < 0 or end <= start:
                raise ExerciseParsingError(
                    "النموذج لم يرجع JSON صالحًا."
                )

            candidate = cleaned[
                start:end + 1
            ]

            try:
                parsed = json.loads(candidate)

            except json.JSONDecodeError as exc:
                logger.error(
                    "Invalid generated JSON preview: %s",
                    candidate[:2000],
                )

                raise ExerciseParsingError(
                    "JSON الناتج غير مكتمل أو غير صالح: "
                    f"{exc}"
                ) from exc

        if not isinstance(parsed, dict):
            raise ExerciseParsingError(
                "إجابة النموذج يجب أن تكون JSON object."
            )

        return parsed