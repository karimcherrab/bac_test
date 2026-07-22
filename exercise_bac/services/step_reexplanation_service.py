import json
import os
import re
from dataclasses import dataclass
from typing import Any

from groq import Groq


class BacStepReExplanationError(Exception):
    """Erreur pendant la génération d'une réexplication d'étape."""


@dataclass
class BacStepReExplanationResult:
    explanation: dict
    model: str


class BacStepReExplanationService:
    """
    خدمة إعادة شرح خطوة من حل تمرين بكالوريا.

    الهدف:
    - شرح الخطوة المختارة فقط.
    - تقديم شرح مفصل وبسيط جدًا.
    - عدم القفز بين العمليات.
    - استعمال LaTeX في جميع الصيغ الرياضية.
    - إعادة JSON صالح ومتوافق مع React.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    # لتجنب إرسال سياق ضخم إلى Groq والتسبب في خطأ 413.
    MAX_STATEMENT_CHARS = 4500
    MAX_QUESTION_CHARS = 2500
    MAX_STRATEGY_CHARS = 2500
    MAX_STEP_TEXT_CHARS = 3000

    def __init__(self, model: str | None = None):
        api_key = os.getenv(
            "API_KEY"
        )
        if not api_key:
            raise BacStepReExplanationError(
                "La variable d'environnement GROQ_API_KEY est absente."
            )

        self.client = Groq(api_key=api_key)

        self.model = model or os.getenv(
            "BAC_REEXPLANATION_MODEL",
            self.DEFAULT_MODEL,
        )

    @staticmethod
    def _safe_text(
        value: Any,
        max_chars: int | None = None,
    ) -> str:
        """
        تحويل القيمة إلى نص وتنظيفها، ثم اختصارها عند الحاجة.
        """
        if value is None:
            return ""

        text = str(value).strip()

        if max_chars and len(text) > max_chars:
            return text[:max_chars].rstrip() + "..."

        return text

    @staticmethod
    def _clean_json_text(value: str) -> str:
        """
        تنظيف إجابة النموذج من Markdown واستخراج كائن JSON.
        """
        text = str(value or "").strip()

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

        text = text.strip()

        # في حال أضاف النموذج كلامًا قبل أو بعد JSON.
        first_brace = text.find("{")
        last_brace = text.rfind("}")

        if (
            first_brace != -1
            and last_brace != -1
            and last_brace > first_brace
        ):
            text = text[first_brace:last_brace + 1]

        return text.strip()

    @staticmethod
    def _normalize_latex_text(value: Any) -> str:
        """
        توحيد بعض محارف LaTeX حتى يستطيع MathJax عرضها بشكل صحيح.
        """
        if value is None:
            return ""

        text = str(value).strip()

        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # معالجة الأقواس المكررة التي قد تصل من JSON.
        text = text.replace("\\\\(", "\\(")
        text = text.replace("\\\\)", "\\)")
        text = text.replace("\\\\[", "\\[")
        text = text.replace("\\\\]", "\\]")

        return text

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        المرور على كامل JSON وتوحيد النصوص وLaTeX.
        """
        if isinstance(value, dict):
            return {
                str(key): cls._normalize_value(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                cls._normalize_value(item)
                for item in value
            ]

        if isinstance(value, str):
            return cls._normalize_latex_text(value)

        return value

    @classmethod
    def _build_step_payload(
        cls,
        step: dict | None,
    ) -> dict | None:
        """
        تحضير بيانات الخطوة دون إرسال بيانات غير ضرورية.
        """
        if not isinstance(step, dict):
            return None

        return {
            "step_number": step.get("step_number"),
            "title": cls._safe_text(
                step.get("title"),
                1000,
            ),
            "explanation": cls._safe_text(
                step.get("explanation"),
                cls.MAX_STEP_TEXT_CHARS,
            ),
            "latex": cls._safe_text(
                step.get("latex"),
                cls.MAX_STEP_TEXT_CHARS,
            ),
        }

    @staticmethod
    def _ensure_string_list(value: Any) -> list[str]:
        """
        ضمان أن الخطوات عبارة عن قائمة نصوص.
        """
        if not isinstance(value, list):
            return []

        result: list[str] = []

        for item in value:
            if isinstance(item, str):
                clean_item = item.strip()

            elif isinstance(item, dict):
                clean_item = str(
                    item.get("explanation")
                    or item.get("text")
                    or item.get("content")
                    or ""
                ).strip()

            else:
                clean_item = str(item or "").strip()

            if clean_item:
                result.append(clean_item)

        return result

    @classmethod
    def _validate_and_normalize_response(
        cls,
        parsed: dict,
    ) -> dict:
        """
        التحقق من بنية جواب النموذج وتجهيزه للواجهة.
        """
        if not isinstance(parsed, dict):
            raise BacStepReExplanationError(
                "La réponse du modèle doit être un objet JSON."
            )

        parsed = cls._normalize_value(parsed)

        title = cls._safe_text(
            parsed.get("title")
            or "شرح مفصل للخطوة"
        )

        detailed_explanation = cls._safe_text(
            parsed.get("detailed_explanation")
            or parsed.get("simple_explanation")
            or parsed.get("explanation")
            or parsed.get("answer")
        )

        why_we_do_this = cls._safe_text(
            parsed.get("why_we_do_this")
        )

        example = cls._safe_text(
            parsed.get("example")
            or parsed.get("mini_example")
        )

        conclusion = cls._safe_text(
            parsed.get("conclusion")
            or parsed.get("summary")
        )

        check_question = cls._safe_text(
            parsed.get("check_question")
        )

        final_answer = cls._safe_text(
            parsed.get("final_answer")
        )

        steps = cls._ensure_string_list(
            parsed.get("steps")
        )

        if not detailed_explanation and not steps:
            raise BacStepReExplanationError(
                "Le modèle n'a pas fourni une explication exploitable."
            )

        return {
            "title": title,
            "simple_explanation": detailed_explanation,
            "detailed_explanation": detailed_explanation,
            "why_we_do_this": why_we_do_this,
            "example": example,
            "steps": steps,
            "conclusion": conclusion,
            "check_question": check_question,
            "final_answer": final_answer,
        }

    @staticmethod
    def _build_system_prompt() -> str:
        return """
أنت أستاذ رياضيات جزائري خبير في شرح تمارين البكالوريا لتلميذ ضعيف جدًا في السنة الثالثة ثانوي.

مهمتك هي إعادة شرح الخطوة المحددة من الحل بطريقة مفصلة جدًا وبسيطة جدًا.

قواعد إلزامية:

1. اشرح فقط الخطوة المطلوبة، مع استعمال السؤال والحل السابق لفهم السياق.

2. لا تعِد حل التمرين كاملًا من البداية، إلا إذا كان تذكير صغير بالخطوة السابقة ضروريًا لفهم الخطوة الحالية.

3. افترض أن الطالب لا يعرف لماذا استعملنا القانون ولا كيف أجرينا العمليات.

4. لا تقفز من عملية إلى النتيجة.

5. قسّم الشرح إلى خطوات صغيرة ومتتابعة.

6. في كل خطوة صغيرة اشرح:
   - ماذا نفعل؟
   - لماذا نفعل ذلك؟
   - ما القانون أو القاعدة المستعملة؟
   - كيف طبقناها؟
   - ماذا استنتجنا؟

7. عند التعويض في قانون:
   - اكتب القانون أولًا.
   - حدّد معنى كل رمز.
   - اكتب القيم التي سنعوّض بها.
   - نفّذ التعويض.
   - نفّذ الحساب مرحلة بمرحلة.

8. لا تستعمل عبارات مثل:
   - من الواضح.
   - بسهولة.
   - مباشرة.
   - نلاحظ فورًا.
   إلا إذا شرحت السبب بعدها.

9. استعمل العربية الفصحى السهلة جدًا، وجملًا قصيرة وواضحة.

10. لا تستعمل كلمات فرنسية أو إنجليزية داخل الشرح إلا عند الضرورة.

11. لا تضف قانونًا غير صحيح أو معلومة غير موجودة في السياق.

12. لا تغيّر النتيجة الرياضية الأصلية الصحيحة.

13. جميع الصيغ والرموز الرياضية يجب أن تكون بصيغة LaTeX.

14. الصيغة الموجودة داخل جملة تكتب هكذا:
\\( u_n = 2n + 1 \\)

15. المعادلة المستقلة تكتب هكذا:
\\[
u_n = 2n + 1
\\]

16. لا تكتب الصيغ الرياضية كنص عادي مثل:
u_n = 2n + 1

17. داخل الحقل latex لا تضع:
\\[
ولا:
\\]
بل ضع محتوى LaTeX فقط إذا استعملت هذا الحقل.

18. لا تستعمل Markdown.

19. لا تستعمل ```json.

20. أرجع كائن JSON صالحًا فقط، دون أي كلام قبله أو بعده.
""".strip()

    @staticmethod
    def _build_user_prompt(context: dict) -> str:
        expected_format = {
            "title": "عنوان قصير وواضح للشرح",
            "detailed_explanation": (
                "شرح تمهيدي مفصل وبسيط جدًا للخطوة، "
                "مع كتابة جميع الصيغ بصيغة LaTeX"
            ),
            "why_we_do_this": (
                "سبب القيام بهذه الخطوة وما فائدتها في الحل"
            ),
            "steps": [
                (
                    "الخطوة الصغيرة الأولى: ماذا نفعل، "
                    "ولماذا، وكيف نفعل ذلك"
                ),
                (
                    "الخطوة الصغيرة الثانية مع العمليات "
                    "والتعويضات بصيغة LaTeX"
                ),
                "الخطوة الصغيرة الثالثة والاستنتاج",
            ],
            "example": (
                "مثال صغير مشابه جدًا، مع حل تدريجي "
                "وصيغ LaTeX"
            ),
            "conclusion": (
                "خلاصة بسيطة توضح ماذا استنتجنا "
                "من الخطوة"
            ),
            "check_question": (
                "سؤال قصير وبسيط للتحقق من فهم الطالب"
            ),
            "final_answer": (
                "النتيجة المرتبطة بهذه الخطوة فقط "
                "بصيغة LaTeX"
            ),
        }

        return (
            "أعد صياغة وشرح الخطوة المحددة بالتفصيل الشديد، "
            "لكن بلغة سهلة جدًا لتلميذ ضعيف.\n\n"
            "يجب ألا تختصر العمليات الحسابية أو التحويلات الجبرية.\n"
            "اجعل قائمة steps تحتوي عادةً على 3 إلى 7 خطوات صغيرة، "
            "حسب حاجة الحل.\n"
            "كل عنصر داخل steps يجب أن يكون نصًا كاملًا مفهومًا.\n\n"
            "بنية JSON المطلوبة بالضبط:\n"
            f"{json.dumps(expected_format, ensure_ascii=False, indent=2)}"
            "\n\n"
            "سياق التمرين والخطوة:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    def generate(
        self,
        *,
        exercise_title: str,
        exercise_year: int,
        statement: str,
        question_text: str,
        strategy: str,
        step: dict,
        previous_step: dict | None = None,
    ) -> BacStepReExplanationResult:
        """
        توليد إعادة شرح مفصلة للخطوة المطلوبة.
        """
        if not isinstance(step, dict):
            raise BacStepReExplanationError(
                "La valeur step doit être un objet JSON."
            )

        step_payload = self._build_step_payload(step)

        if not step_payload:
            raise BacStepReExplanationError(
                "La étape à expliquer est absente."
            )

        previous_payload = self._build_step_payload(
            previous_step
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
            "solution_strategy": self._safe_text(
                strategy,
                self.MAX_STRATEGY_CHARS,
            ),
            "previous_step": previous_payload,
            "step_to_explain": step_payload,
        }

        system_prompt = self._build_system_prompt()

        user_prompt = self._build_user_prompt(
            context
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0.15,
                max_tokens=1800,
                response_format={
                    "type": "json_object",
                },
            )

        except Exception as exc:
            raise BacStepReExplanationError(
                f"Échec de connexion au modèle IA: {exc}"
            ) from exc

        if not response.choices:
            raise BacStepReExplanationError(
                "Le modèle n'a retourné aucune réponse."
            )

        content = response.choices[0].message.content

        if not content:
            raise BacStepReExplanationError(
                "Le modèle a retourné une réponse vide."
            )

        clean_content = self._clean_json_text(
            content
        )

        try:
            parsed = json.loads(clean_content)

        except (TypeError, json.JSONDecodeError) as exc:
            raise BacStepReExplanationError(
                "Le modèle n'a pas retourné un JSON valide."
            ) from exc

        explanation = self._validate_and_normalize_response(
            parsed
        )

        return BacStepReExplanationResult(
            explanation=explanation,
            model=self.model,
        )