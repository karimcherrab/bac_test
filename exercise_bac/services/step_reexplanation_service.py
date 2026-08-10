import json
import os
import re
from dataclasses import dataclass
from typing import Any

from groq import Groq


class BacStepReExplanationError(Exception):
    """Erreur pendant la génération d'une réexplication de question."""


@dataclass
class BacStepReExplanationResult:
    explanation: dict
    model: str


class BacStepReExplanationService:
    """
    خدمة إعادة شرح سؤال كامل من تمرين بكالوريا.

    التعديل الأساسي:
    - لم نعد نشرح step واحدة.
    - نرسل نص السؤال والحل الكامل المخزن.
    - النموذج يعيد شرح السؤال من البداية حتى النتيجة
      بلغة بسيطة ومنظمة.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    MAX_STATEMENT_CHARS = 4500
    MAX_QUESTION_CHARS = 3000
    MAX_SOLUTION_CHARS = 9000

    def __init__(
        self,
        model: str | None = None,
    ):
        api_key = (
            os.getenv("GROQ_API_KEY")
            or os.getenv("API_KEY")
        )

        if not api_key:
            raise BacStepReExplanationError(
                "La variable GROQ_API_KEY "
                "ou API_KEY est absente."
            )

        self.client = Groq(
            api_key=api_key
        )

        self.model = (
            model
            or os.getenv(
                "BAC_REEXPLANATION_MODEL",
                self.DEFAULT_MODEL,
            )
        )

    @staticmethod
    def _safe_text(
        value: Any,
        max_chars: int | None = None,
    ) -> str:
        if value is None:
            return ""

        text = str(value).strip()

        if (
            max_chars
            and len(text) > max_chars
        ):
            return (
                text[:max_chars]
                .rstrip()
                + "..."
            )

        return text

    @staticmethod
    def _clean_json_text(
        value: str,
    ) -> str:
        text = str(
            value or ""
        ).strip()

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        first_brace = text.find("{")
        last_brace = text.rfind("}")

        if (
            first_brace != -1
            and last_brace != -1
            and last_brace > first_brace
        ):
            text = text[
                first_brace:
                last_brace + 1
            ]

        return text.strip()

    @staticmethod
    def _normalize_latex_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        text = str(value).strip()

        text = text.replace(
            "\r\n",
            "\n",
        )

        text = text.replace(
            "\r",
            "\n",
        )

        text = text.replace(
            "\\\\(",
            "\\(",
        )

        text = text.replace(
            "\\\\)",
            "\\)",
        )

        text = text.replace(
            "\\\\[",
            "\\[",
        )

        text = text.replace(
            "\\\\]",
            "\\]",
        )

        return text

    @classmethod
    def _normalize_value(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(value, dict):
            return {
                str(key): cls._normalize_value(
                    item
                )
                for key, item
                in value.items()
            }

        if isinstance(value, list):
            return [
                cls._normalize_value(
                    item
                )
                for item in value
            ]

        if isinstance(value, str):
            return (
                cls._normalize_latex_text(
                    value
                )
            )

        return value

    @staticmethod
    def _ensure_string_list(
        value: Any,
    ) -> list[str]:
        if not isinstance(
            value,
            list,
        ):
            return []

        result = []

        for item in value:
            if isinstance(
                item,
                str,
            ):
                clean_item = (
                    item.strip()
                )

            elif isinstance(
                item,
                dict,
            ):
                clean_item = str(
                    item.get(
                        "explanation"
                    )
                    or item.get(
                        "text"
                    )
                    or item.get(
                        "content"
                    )
                    or item.get(
                        "result"
                    )
                    or ""
                ).strip()

            else:
                clean_item = str(
                    item or ""
                ).strip()

            if clean_item:
                result.append(
                    clean_item
                )

        return result

    @classmethod
    def _compact_solution(
        cls,
        solution: dict,
    ) -> dict:
        """
        نرسل فقط المعلومات المفيدة للشرح
        حتى لا يصبح الـ prompt ضخمًا.
        """
        if not isinstance(
            solution,
            dict,
        ):
            return {}

        compact = {}

        useful_keys = (
            "main_idea",
            "detailed_explanation",
            "strategy",
            "methodology",
            "steps",
            "conclusion",
            "final_answer",
            "verification",
            "hints",
            "common_mistakes",
        )

        for key in useful_keys:
            if key in solution:
                compact[key] = (
                    solution[key]
                )

        serialized = json.dumps(
            compact,
            ensure_ascii=False,
        )

        if (
            len(serialized)
            <= cls.MAX_SOLUTION_CHARS
        ):
            return compact

        # إذا كان الحل كبيرًا جدًا نحتفظ بأهم
        # العناصر مع عدد محدود من الخطوات.
        steps = solution.get(
            "steps",
            [],
        )

        if isinstance(
            steps,
            dict,
        ):
            steps = list(
                steps.values()
            )

        if not isinstance(
            steps,
            list,
        ):
            steps = []

        return {
            "main_idea": solution.get(
                "main_idea",
                "",
            ),
            "strategy": solution.get(
                "strategy",
                "",
            ),
            "steps": steps[:12],
            "conclusion": solution.get(
                "conclusion",
                "",
            ),
            "final_answer": solution.get(
                "final_answer",
                "",
            ),
            "verification": solution.get(
                "verification",
                "",
            ),
        }

    @classmethod
    def _validate_and_normalize_response(
        cls,
        parsed: dict,
    ) -> dict:
        if not isinstance(
            parsed,
            dict,
        ):
            raise (
                BacStepReExplanationError(
                    "La réponse du modèle "
                    "doit être un objet JSON."
                )
            )

        parsed = cls._normalize_value(
            parsed
        )

        title = cls._safe_text(
            parsed.get("title")
            or "شرح مبسط للسؤال"
        )

        detailed_explanation = (
            cls._safe_text(
                parsed.get(
                    "detailed_explanation"
                )
                or parsed.get(
                    "simple_explanation"
                )
                or parsed.get(
                    "explanation"
                )
                or parsed.get(
                    "answer"
                )
            )
        )

        why_we_do_this = (
            cls._safe_text(
                parsed.get(
                    "why_we_do_this"
                )
            )
        )

        example = cls._safe_text(
            parsed.get("example")
            or parsed.get(
                "mini_example"
            )
        )

        conclusion = cls._safe_text(
            parsed.get("conclusion")
            or parsed.get("summary")
        )

        check_question = (
            cls._safe_text(
                parsed.get(
                    "check_question"
                )
            )
        )

        final_answer = (
            cls._safe_text(
                parsed.get(
                    "final_answer"
                )
            )
        )

        steps = (
            cls._ensure_string_list(
                parsed.get("steps")
            )
        )

        if (
            not detailed_explanation
            and not steps
        ):
            raise (
                BacStepReExplanationError(
                    "Le modèle n'a pas "
                    "fourni une explication "
                    "exploitable."
                )
            )

        return {
            "title": title,
            "simple_explanation": (
                detailed_explanation
            ),
            "detailed_explanation": (
                detailed_explanation
            ),
            "why_we_do_this": (
                why_we_do_this
            ),
            "example": example,
            "steps": steps,
            "conclusion": conclusion,
            "check_question": (
                check_question
            ),
            "final_answer": (
                final_answer
            ),
        }

    @staticmethod
    def _build_system_prompt() -> str:
        return r"""
أنت أستاذ جزائري خبير في شرح تمارين البكالوريا لتلميذ السنة الثالثة ثانوي.

مهمتك هي إعادة شرح السؤال المطلوب كاملًا، وليس شرح خطوة واحدة فقط.

قواعد إلزامية:

1. ابدأ بفهم المطلوب في السؤال بلغة سهلة جدًا.

2. اشرح الفكرة التي تسمح بحل السؤال قبل الحساب.

3. استعمل الحل الأصلي المخزن كمرجع حتى تحافظ على نفس الطريقة والنتيجة الصحيحة.

4. أعد شرح الحل كاملًا من بداية السؤال حتى النتيجة النهائية.

5. قسّم الحل إلى خطوات صغيرة ومتتابعة.

6. في كل خطوة اشرح:
- ماذا نفعل؟
- لماذا نفعل ذلك؟
- ما القانون أو القاعدة المستعملة؟
- كيف طبقناها؟
- ماذا استنتجنا؟

7. عند استعمال قانون:
- اكتب القانون.
- اشرح معنى الرموز عند الحاجة.
- عوض بالقيم.
- نفذ الحساب تدريجيًا.

8. لا تقفز مباشرة من المعطيات إلى النتيجة.

9. استعمل العربية الفصحى السهلة والواضحة.

10. لا تغيّر النتيجة الرياضية الصحيحة الموجودة في الحل الأصلي.

11. لا تضف معلومات أو قوانين غير ضرورية خارج السؤال.

12. جميع الصيغ الرياضية تستعمل LaTeX.

13. الصيغة داخل الجملة:
\( u_n = 2n + 1 \)

14. المعادلة المستقلة:
\[
u_n = 2n + 1
\]

15. لا تستعمل Markdown.

16. لا تستعمل ```json.

17. أرجع كائن JSON صالحًا فقط، دون أي كلام قبله أو بعده.
""".strip()

    @staticmethod
    def _build_user_prompt(
        context: dict,
    ) -> str:
        expected_format = {
            "title": (
                "عنوان قصير مثل: "
                "شرح السؤال بطريقة مبسطة"
            ),
            "detailed_explanation": (
                "اشرح أولًا ماذا يطلب "
                "السؤال وما الفكرة الأساسية "
                "التي سنستعملها"
            ),
            "why_we_do_this": (
                "لماذا اخترنا هذه الطريقة "
                "أو هذا القانون"
            ),
            "steps": [
                (
                    "الخطوة الأولى من حل "
                    "السؤال مع السبب"
                ),
                (
                    "الخطوة الثانية مع "
                    "التعويض والحساب"
                ),
                (
                    "الاستنتاج والوصول "
                    "إلى النتيجة"
                ),
            ],
            "example": (
                "مثال صغير مشابه فقط إذا "
                "كان مفيدًا للفهم"
            ),
            "conclusion": (
                "خلاصة قصيرة لما فعلناه"
            ),
            "check_question": (
                "سؤال تحقق بسيط للتلميذ"
            ),
            "final_answer": (
                "النتيجة النهائية لنفس السؤال"
            ),
        }

        return (
            "أعد شرح السؤال التالي كاملًا "
            "من البداية حتى النتيجة، "
            "ولا تشرح خطوة منفردة.\n\n"
            "حافظ على نفس النتيجة الصحيحة "
            "الموجودة في الحل الأصلي.\n\n"
            "بنية JSON المطلوبة:\n"
            f"{json.dumps(expected_format, ensure_ascii=False, indent=2)}"
            "\n\n"
            "سياق التمرين والسؤال والحل:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    def generate(
        self,
        *,
        exercise_title: str,
        exercise_year: int,
        statement: str,
        question_text: str,
        solution: dict,
    ) -> BacStepReExplanationResult:
        if not isinstance(
            solution,
            dict,
        ):
            raise (
                BacStepReExplanationError(
                    "La solution de la "
                    "question est absente."
                )
            )

        compact_solution = (
            self._compact_solution(
                solution
            )
        )

        context = {
            "exercise": {
                "title": self._safe_text(
                    exercise_title,
                    1000,
                ),
                "year": exercise_year,
                "statement": self._safe_text(
                    statement,
                    self.MAX_STATEMENT_CHARS,
                ),
            },
            "question": self._safe_text(
                question_text,
                self.MAX_QUESTION_CHARS,
            ),
            "original_solution": (
                compact_solution
            ),
        }

        system_prompt = (
            self._build_system_prompt()
        )

        user_prompt = (
            self._build_user_prompt(
                context
            )
        )

        try:
            response = (
                self.client
                .chat
                .completions
                .create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                system_prompt
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                user_prompt
                            ),
                        },
                    ],
                    temperature=0.15,
                    max_tokens=2400,
                    response_format={
                        "type": "json_object",
                    },
                )
            )

        except Exception as exc:
            raise (
                BacStepReExplanationError(
                    "Échec de connexion "
                    f"au modèle IA: {exc}"
                )
            ) from exc

        if not response.choices:
            raise (
                BacStepReExplanationError(
                    "Le modèle n'a retourné "
                    "aucune réponse."
                )
            )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:
            raise (
                BacStepReExplanationError(
                    "Le modèle a retourné "
                    "une réponse vide."
                )
            )

        clean_content = (
            self._clean_json_text(
                content
            )
        )

        try:
            parsed = json.loads(
                clean_content
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise (
                BacStepReExplanationError(
                    "Le modèle n'a pas "
                    "retourné un JSON valide."
                )
            ) from exc

        explanation = (
            self
            ._validate_and_normalize_response(
                parsed
            )
        )

        return (
            BacStepReExplanationResult(
                explanation=explanation,
                model=self.model,
            )
        )
