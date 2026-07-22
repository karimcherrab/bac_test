import json
import re
from typing import Any

from knowledge.retrieval.answer_generator import (
    AnswerGenerator,
)
from knowledge.retrieval.context_builder import (
    BuiltContext,
)


class ReExplainStepService:
    """
    يجيب عن سؤال التلميذ اعتمادًا على المرحلة الحالية فقط.

    إذا كان السؤال خارج المرحلة:
    - لا يجيب عن الموضوع الخارجي.
    - يعيد is_related=False.
    """

    MAX_STEPS = 4

    # أقصى حجم لمحتوى المرحلة المرسل إلى النموذج.
    MAX_STEP_CONTENT_CHARS = 5500

    def __init__(self):
        self.generator = AnswerGenerator()

    def clean_model_response(
        self,
        text: str,
    ) -> str:
        if not text:
            return ""

        text = str(text).strip()

        text = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```\s*$",
            "",
            text,
        )

        return text.strip()

    def extract_json(
        self,
        text: str,
    ) -> dict:
        cleaned = self.clean_model_response(
            text
        )

        if not cleaned:
            return self.get_fallback_answer(
                message=(
                    "لم أتمكن من إنشاء جواب مناسب. "
                    "أعد كتابة السؤال بطريقة أوضح."
                )
            )

        try:
            parsed = json.loads(cleaned)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if (
            start != -1
            and end != -1
            and end > start
        ):
            try:
                parsed = json.loads(
                    cleaned[start:end + 1]
                )

                if isinstance(parsed, dict):
                    return parsed

            except json.JSONDecodeError:
                pass

        return self.get_fallback_answer(
            message=cleaned
        )

    def normalize_text(
        self,
        value: Any,
        default: str = "",
    ) -> str:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.strip()

            return value or default

        value = str(value).strip()

        return value or default

    def normalize_boolean(
        self,
        value: Any,
        default: bool = True,
    ) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return value != 0

        if isinstance(value, str):
            normalized = value.strip().lower()

            if normalized in {
                "true",
                "1",
                "yes",
                "oui",
                "نعم",
                "مرتبط",
                "related",
            }:
                return True

            if normalized in {
                "false",
                "0",
                "no",
                "non",
                "لا",
                "غير مرتبط",
                "unrelated",
            }:
                return False

        return default

    def normalize_steps(
        self,
        value: Any,
    ) -> list[str]:
        if not isinstance(value, list):
            return []

        normalized_steps = []

        for item in value:
            if isinstance(item, dict):
                text = (
                    item.get("text")
                    or item.get("instruction")
                    or item.get("explanation")
                    or item.get("step")
                    or item.get("title")
                    or ""
                )
            else:
                text = item

            text = self.normalize_text(text)

            if text:
                normalized_steps.append(text)

        return normalized_steps[:self.MAX_STEPS]

    def get_fallback_answer(
        self,
        message: str = "",
    ) -> dict:
        return {
            "is_related": True,
            "relation_reason": "",
            "title": "توضيح المرحلة",
            "simple_explanation": (
                message
                or "لم أتمكن من إنشاء شرح مناسب."
            ),
            "example": "",
            "steps": [],
            "check_question": "",
            "expected_answer": "",
            "encouragement": (
                "أعد صياغة الجزء الذي لم تفهمه."
            ),
        }

    def get_unrelated_answer(
        self,
        relation_reason: str = "",
    ) -> dict:
        return {
            "is_related": False,
            "relation_reason": (
                relation_reason
                or (
                    "السؤال لا يتعلق بالمفهوم "
                    "الموجود في المرحلة الحالية."
                )
            ),
            "title": (
                "السؤال غير متعلق بهذه المرحلة"
            ),
            "simple_explanation": (
                "هذا السؤال غير متعلق بالمحتوى "
                "الموجود في هذه المرحلة. "
                "اختر المرحلة المناسبة ثم أعد طرحه."
            ),
            "example": "",
            "steps": [],
            "check_question": "",
            "expected_answer": "",
            "encouragement": (
                "اطرح سؤالًا حول الفكرة الموجودة "
                "في المرحلة الحالية."
            ),
        }

    def normalize_answer(
        self,
        answer: dict,
        step_title: str,
    ) -> dict:
        if not isinstance(answer, dict):
            answer = {
                "simple_explanation": (
                    self.normalize_text(answer)
                )
            }

        is_related = self.normalize_boolean(
            answer.get("is_related"),
            default=True,
        )

        relation_reason = self.normalize_text(
            answer.get("relation_reason")
        )

        if not is_related:
            return self.get_unrelated_answer(
                relation_reason=relation_reason,
            )

        simple_explanation = self.normalize_text(
            answer.get("simple_explanation")
            or answer.get("explanation")
            or answer.get("answer")
        )

        if not simple_explanation:
            simple_explanation = (
                "لم يتم إنشاء شرح واضح. "
                "حاول إعادة صياغة السؤال."
            )

        return {
            "is_related": True,
            "relation_reason": relation_reason,
            "title": self.normalize_text(
                answer.get("title"),
                f"توضيح: {step_title}",
            ),
            "simple_explanation": (
                simple_explanation
            ),
            "example": self.normalize_text(
                answer.get("example")
            ),
            "steps": self.normalize_steps(
                answer.get("steps")
            ),
            "check_question": self.normalize_text(
                answer.get("check_question")
            ),
            "expected_answer": self.normalize_text(
                answer.get("expected_answer")
            ),
            "encouragement": self.normalize_text(
                answer.get("encouragement"),
                "لا بأس، سنفهمها خطوة بخطوة.",
            ),
        }

    def compact_value(
        self,
        value: Any,
        depth: int = 0,
    ) -> Any:
        """
        تنظيف محتوى المرحلة قبل إرساله للنموذج.

        يحذف:
        - القيم الفارغة.
        - البيانات الرسومية الكبيرة.
        - الحقول التقنية.
        - القوائم الطويلة.
        """

        if depth > 5:
            return None

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

            # منع النصوص الطويلة جدًا داخل حقل واحد.
            return value[:1800]

        if isinstance(
            value,
            (int, float, bool),
        ):
            return value

        if isinstance(value, list):
            cleaned_items = []

            # نرسل أول 8 عناصر فقط.
            for item in value[:8]:
                cleaned_item = self.compact_value(
                    item,
                    depth=depth + 1,
                )

                if cleaned_item not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    cleaned_items.append(
                        cleaned_item
                    )

            return cleaned_items

        if isinstance(value, dict):
            ignored_keys = {
                "graph_data",
                "graph",
                "series",
                "annotations",
                "settings",
                "x_domain",
                "y_domain",
                "created_at",
                "updated_at",
                "metadata",
                "dynamic_profile",
            }

            cleaned_dict = {}

            for key, nested_value in value.items():
                if key in ignored_keys:
                    continue

                cleaned_value = self.compact_value(
                    nested_value,
                    depth=depth + 1,
                )

                if cleaned_value not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    cleaned_dict[key] = (
                        cleaned_value
                    )

            return cleaned_dict

        return str(value)[:1000]

    def prepare_step_content(
        self,
        step: dict,
    ) -> str:
        content = step.get(
            "content",
            {},
        )

        compact_content = self.compact_value(
            content
        )

        # separators بدون مسافات لتقليل حجم الـTokens.
        content_json = json.dumps(
            compact_content,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

        if (
            len(content_json)
            > self.MAX_STEP_CONTENT_CHARS
        ):
            content_json = content_json[
                :self.MAX_STEP_CONTENT_CHARS
            ]

        return content_json

    def build_prompt(
            self,
            step: dict,
            student_question: str,
    ) -> str:
        step_title = self.normalize_text(
            step.get("title"),
            "مرحلة من الدرس",
        )

        step_type = self.normalize_text(
            step.get("type"),
            "explanation",
        )

        content_json = self.prepare_step_content(
            step
        )

        student_question = self.normalize_text(
            student_question
        )[:1200]

        return f"""
    أنت أستاذ رياضيات جزائري تجيب عن سؤال تلميذ بكالوريا.

    مرجع المرحلة الحالية:
    العنوان: {step_title}
    النوع: {step_type}
    المحتوى: {content_json}

    السؤال الحقيقي الذي كتبه التلميذ:
    {student_question}

    أجب عن السؤال المكتوب أعلاه نفسه فقط.

    تعليمات إلزامية:
    - استخرج جميع المعطيات الرياضية الموجودة في سؤال التلميذ.
    - لا تقل إن المعطيات ناقصة إذا كانت موجودة في السؤال.
    - لا تنقل معطيات السؤال إلى سؤال تحقق جديد دون حلها أولًا.
    - لا تحول السؤال إلى تعريف عام أو درس عام.
    - لا تغير التعبير أو الأعداد أو الرموز التي كتبها التلميذ.
    - إذا طلب قيمة، احسبها وأعط النتيجة مباشرة.
    - إذا طلب تفسيرًا، فسر النقطة المطلوبة فقط.
    - إذا طلب طريقة، طبقها على معطياته.
    - ابدأ simple_explanation بجواب مباشر عن السؤال.
    - يجب أن تعتمد steps على معطيات سؤال التلميذ نفسه.
    - لا تخترع مثالًا بدل حل السؤال.
    - لا تقل: أرسل الصيغة، أعطني الحدود، المعطيات غير كافية؛
      إلا إذا كان سؤال التلميذ فعلًا خاليًا تمامًا من المعطيات الضرورية.
    - تحقق من صحة الحساب قبل الإجابة.
    - استعمل عربية بسيطة وواضحة.
    - استعمل من خطوة واحدة إلى ثلاث خطوات فقط.
    - لا تستعمل Markdown.
    - أرجع JSON صحيحًا فقط.

    مثال إلزامي لفهم طريقة الإجابة:

    السؤال:
    ما هو أساس المتتالية u_n = 5n + 2؟

    الجواب:
    - النتيجة: r = 5.
    - لأن معامل n هو 5.
    - ويمكن التحقق بحساب:
      u_(n+1) - u_n = 5.

    لا تقل:
    لا يمكن حساب الأساس دون معرفة صيغة المتتالية؛
    لأن الصيغة موجودة فعلًا في السؤال.

    شكل JSON المطلوب:

    {{
      "title": "عنوان يطابق سؤال التلميذ",
      "direct_answer": "النتيجة المباشرة لسؤال التلميذ",
      "simple_explanation": "شرح الجواب باستعمال معطيات التلميذ نفسها",
      "steps": [
        "خطوة مرتبطة مباشرة بالسؤال",
        "خطوة مرتبطة مباشرة بالسؤال"
      ],
      "check_question": "",
      "expected_answer": "",
      "encouragement": "جملة قصيرة"
    }}
    """.strip()

    def generate(
            self,
            step: dict,
            student_question: str,
    ) -> dict:
        step_id = self.normalize_text(
            step.get("id")
        )

        step_title = self.normalize_text(
            step.get("title"),
            "مرحلة من الدرس",
        )

        student_question = self.normalize_text(
            student_question
        )

        if not student_question:
            raise ValueError(
                "سؤال التلميذ فارغ."
            )

        # حماية من الطلبات الكبيرة.
        student_question = student_question[:1200]

        prompt = self.build_prompt(
            step=step,
            student_question=student_question,
        )

        context = BuiltContext(
            # السؤال موجود داخل prompt بالفعل.
            # نضع نصًا قصيرًا هنا لأن AnswerGenerator
            # قد يحتاج question غير فارغ.
            question="أجب عن سؤال التلميذ الموجود في السياق.",
            intent="re_explain_step",
            context_text=prompt,
            items=[],
        )

        generated = self.generator.generate(
            context
        )

        parsed_answer = self.extract_json(
            generated.answer
        )

        normalized_answer = self.normalize_answer(
            answer=parsed_answer,
            step_title=step_title,
        )

        return {
            "mode": "re_explain_step",
            "step_id": step_id,
            "step_title": step_title,
            "model": self.normalize_text(
                generated.model
            ),
            "answer": normalized_answer,
        }