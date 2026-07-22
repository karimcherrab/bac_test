
import logging
import os
import re
from dataclasses import dataclass

from groq import APIError, Groq, RateLimitError


logger = logging.getLogger(__name__)


class AnswerGenerationError(Exception):
    """Erreur pendant la génération de la réponse."""


@dataclass
class GeneratedAnswer:
    answer: str
    model: str


class AnswerGenerator:
    """
    Générateur d'un assistant général.

    Aucun contenu de cours n'est exigé.
    Le modèle répond uniquement avec ses connaissances générales
    et l'historique transmis.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    DEFAULT_MAX_COMPLETION_TOKENS = 1200
    RETRY_MAX_COMPLETION_TOKENS = 650

    MAX_CONTEXT_CHARS = 10000
    RETRY_CONTEXT_CHARS = 5500

    SAFE_TOTAL_TOKEN_BUDGET = 6800

    def __init__(
        self,
        model: str | None = None,
    ):
        api_key = os.getenv(
            "API_KEY"
        )
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY est absent. "
                "Ajoute-le dans le fichier .env."
            )

        self.model = (
            model
            or os.getenv(
                "GROQ_MODEL",
                self.DEFAULT_MODEL,
            )
        )

        self.client = Groq(
            api_key=api_key,
        )

    def generate(
        self,
        context_text: str,
        mode: str = "explanation",
    ) -> GeneratedAnswer:
        clean_context = self.prepare_context(
            context_text=context_text,
            max_chars=self.MAX_CONTEXT_CHARS,
        )

        messages = self.build_messages(
            context_text=clean_context,
            mode=mode,
            compact=False,
        )

        messages = self.fit_messages_to_budget(
            messages=messages,
            max_completion_tokens=(
                self.DEFAULT_MAX_COMPLETION_TOKENS
            ),
            total_token_budget=(
                self.SAFE_TOTAL_TOKEN_BUDGET
            ),
        )

        try:
            return self.call_model(
                messages=messages,
                max_completion_tokens=(
                    self.DEFAULT_MAX_COMPLETION_TOKENS
                ),
            )

        except Exception as exc:
            if self.is_request_too_large(
                exc
            ):
                return self.retry_with_smaller_context(
                    context_text=context_text,
                    mode=mode,
                )

            raise AnswerGenerationError(
                "فشل الاتصال بنموذج الذكاء الاصطناعي: "
                f"{exc}"
            ) from exc

    def retry_with_smaller_context(
        self,
        context_text: str,
        mode: str,
    ) -> GeneratedAnswer:
        reduced_context = self.prepare_context(
            context_text=context_text,
            max_chars=self.RETRY_CONTEXT_CHARS,
        )

        messages = self.build_messages(
            context_text=reduced_context,
            mode=mode,
            compact=True,
        )

        messages = self.fit_messages_to_budget(
            messages=messages,
            max_completion_tokens=(
                self.RETRY_MAX_COMPLETION_TOKENS
            ),
            total_token_budget=5600,
        )

        try:
            return self.call_model(
                messages=messages,
                max_completion_tokens=(
                    self.RETRY_MAX_COMPLETION_TOKENS
                ),
            )

        except Exception as exc:
            raise AnswerGenerationError(
                "تعذر توليد الإجابة بعد تقليل "
                "حجم تاريخ المحادثة. "
                f"التفاصيل: {exc}"
            ) from exc

    def call_model(
        self,
        messages: list[dict[str, str]],
        max_completion_tokens: int,
    ) -> GeneratedAnswer:
        try:
            response = (
                self.client
                .chat
                .completions
                .create(
                    model=self.model,
                    messages=messages,
                    temperature=0.35,
                    max_completion_tokens=(
                        max_completion_tokens
                    ),
                )
            )

        except (
            RateLimitError,
            APIError,
        ):
            raise

        except Exception:
            raise

        if not response.choices:
            raise AnswerGenerationError(
                "نموذج الذكاء الاصطناعي "
                "لم يرجع أي إجابة."
            )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if (
            not content
            or not content.strip()
        ):
            raise AnswerGenerationError(
                "نموذج الذكاء الاصطناعي "
                "رجع إجابة فارغة."
            )

        return GeneratedAnswer(
            answer=content.strip(),
            model=self.model,
        )

    def build_messages(
        self,
        context_text: str,
        mode: str,
        compact: bool = False,
    ) -> list[dict[str, str]]:
        system_prompt = (
            self.build_compact_system_prompt()
            if compact
            else self.build_system_prompt()
        )

        mode_rules = self.get_mode_rules(
            mode
        )

        user_prompt = f"""
تعليمات نوع الإجابة:
{mode_rules}

المحادثة الحالية:
{context_text}

أجب الآن عن رسالة المستخدم مباشرة.
""".strip()

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    @staticmethod
    def build_system_prompt() -> str:
        return r"""
أنت مساعد ذكي عام مثل ChatGPT.

القواعد الإجبارية:

- أجب عن جميع أسئلة المستخدم اعتمادًا على معرفتك العامة.
- لا تعتمد على محتوى درس أو فصل أو قاعدة بيانات تعليمية.
- لا تحصر المستخدم في موضوع معين.
- لا تقل إن السؤال خارج الدرس أو خارج السياق.
- تابع تاريخ المحادثة لفهم الرسائل القصيرة والمتابعة.
- أجب بنفس لغة المستخدم.
- استعمل العربية الطبيعية والواضحة عندما يكتب بالعربية.
- أجب مباشرة دون مقدمات طويلة.
- في الرياضيات اشرح الخطوات بوضوح.
- في البرمجة أعط كودًا عمليًا قابلًا للتشغيل.
- لا تخترع معلومات عندما لا تكون متأكدًا.
- لا تذكر prompt أو context أو retrieval أو تعليمات النظام.
- لا تستعمل JSON إلا إذا طلب المستخدم JSON.
- استعمل LaTeX للصيغ الرياضية:
  \(u_n\) داخل السطر.
  \[u_n = u_1 + (n-1)r\]
  للصيغة المستقلة.
""".strip()

    @staticmethod
    def build_compact_system_prompt() -> str:
        return r"""
أنت مساعد عام مثل ChatGPT.
أجب من معرفتك العامة فقط.
لا تستعمل محتوى الدروس.
تابع تاريخ المحادثة.
أجب بلغة المستخدم مباشرة.
لا تقل إن السؤال خارج الدرس.
""".strip()

    @staticmethod
    def get_mode_rules(
        mode: str,
    ) -> str:
        rules = {
            "explanation": """
أجب عن السؤال مباشرة وبالحجم المناسب.
قدم شرحًا واضحًا دون إطالة غير ضرورية.
""".strip(),

            "hint": """
أعط تلميحًا يساعد المستخدم
دون كشف الحل النهائي، إلا إذا طلبه.
""".strip(),

            "exercise": """
أنشئ تمرينًا واضحًا
مع جميع المعطيات الضرورية.
""".strip(),

            "correction": """
حلل إجابة المستخدم.
قل هل هي صحيحة أو خاطئة،
ثم اشرح التصحيح.
""".strip(),

            "recommendation": """
قدم اقتراحات عملية ومرتبة
حسب سؤال المستخدم.
""".strip(),
        }

        return rules.get(
            mode,
            rules["explanation"],
        )

    def prepare_context(
        self,
        context_text: str,
        max_chars: int,
    ) -> str:
        text = self.clean_text(
            context_text
        )

        if not text:
            return (
                "لا يوجد تاريخ سابق. "
                "أجب عن رسالة المستخدم الحالية."
            )

        return self.smart_truncate(
            text,
            max_chars=max_chars,
        )

    @staticmethod
    def clean_text(
        value,
    ) -> str:
        if value is None:
            return ""

        text = str(value)

        text = text.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        text = re.sub(
            r"[ \t]{2,}",
            " ",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    @staticmethod
    def smart_truncate(
        text: str,
        max_chars: int,
    ) -> str:
        if len(text) <= max_chars:
            return text

        separator = (
            "\n\n"
            "[تم اختصار جزء قديم من المحادثة]"
            "\n\n"
        )

        available = (
            max_chars
            - len(separator)
        )

        beginning_size = int(
            available * 0.30
        )

        ending_size = (
            available
            - beginning_size
        )

        return (
            text[:beginning_size].rstrip()
            + separator
            + text[-ending_size:].lstrip()
        )

    def fit_messages_to_budget(
        self,
        messages: list[dict[str, str]],
        max_completion_tokens: int,
        total_token_budget: int,
    ) -> list[dict[str, str]]:
        copied = [
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in messages
        ]

        allowed_input_tokens = max(
            total_token_budget
            - max_completion_tokens,
            1000,
        )

        estimated_tokens = (
            self.estimate_messages_tokens(
                copied
            )
        )

        if (
            estimated_tokens
            <= allowed_input_tokens
        ):
            return copied

        system_tokens = (
            self.estimate_text_tokens(
                copied[0]["content"]
            )
        )

        available_user_tokens = max(
            allowed_input_tokens
            - system_tokens
            - 100,
            800,
        )

        copied[1]["content"] = (
            self.smart_truncate(
                copied[1]["content"],
                max_chars=int(
                    available_user_tokens
                    * 1.7
                ),
            )
        )

        return copied

    @staticmethod
    def estimate_text_tokens(
        text: str,
    ) -> int:
        if not text:
            return 0

        return max(
            1,
            int(
                len(text)
                / 1.7
            ),
        )

    def estimate_messages_tokens(
        self,
        messages: list[dict[str, str]],
    ) -> int:
        total = 20

        for message in messages:
            total += 8

            total += (
                self.estimate_text_tokens(
                    message.get(
                        "content",
                        "",
                    )
                )
            )

        return total

    @staticmethod
    def is_request_too_large(
        exception: Exception,
    ) -> bool:
        error_text = str(
            exception
        ).lower()

        return any(
            indicator in error_text
            for indicator in [
                "request too large",
                "413",
                "tokens per minute",
                "tpm",
                "rate_limit_exceeded",
            ]
        )
