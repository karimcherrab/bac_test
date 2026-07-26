import inspect
import json
import logging
import math
import re
from typing import Any, Literal

from knowledge.retrieval.answer_generator import AnswerGenerator
from knowledge.retrieval.context_builder import BuiltContext

logger = logging.getLogger(__name__)

RequestType = Literal["explanation", "example"]


class ReExplainStepService:
    """إنشاء شرح مبسط ومفصل أو مثال واحد لمرحلة محددة فقط."""

    MAX_STEP_CONTENT_CHARS = 6000
    MAX_STUDENT_QUESTION_CHARS = 700
    MAX_CONTENT_CHARS = 4000
    MAX_GRAPH_SERIES = 2
    MAX_GRAPH_POINTS = 40
    ALLOWED_REQUEST_TYPES = {"explanation", "example"}

    def __init__(self):
        self.generator = AnswerGenerator()

    @staticmethod
    def normalize_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        value = str(value).strip()
        return value or default

    @staticmethod
    def clean_model_response(text: Any) -> str:
        text = str(text or "").strip()
        text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```\s*$", "", text)
        return text.strip()

    def fallback_answer(self, request_type: RequestType, message: str = "") -> dict:
        default_message = (
            "تعذّر إنشاء المثال الآن. أعد المحاولة مرة أخرى."
            if request_type == "example"
            else "تعذّر إنشاء الشرح الآن. أعد المحاولة مرة أخرى."
        )
        return {
            "type": request_type,
            "content": self.normalize_text(message, default_message)[: self.MAX_CONTENT_CHARS],
            "graph": None,
        }

    def extract_json(self, text: Any, request_type: RequestType) -> dict:
        cleaned = self.clean_model_response(text)
        if not cleaned:
            return self.fallback_answer(request_type)

        candidates = [cleaned]
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            candidates.append(cleaned[start : end + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        # لا نعرض JSON تالفًا أو تعليمات تقنية للتلميذ.
        plain_text = re.sub(r"[{}\[\]\"]", " ", cleaned)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        return self.fallback_answer(request_type, plain_text)

    def compact_value(self, value: Any, depth: int = 0) -> Any:
        if depth > 6 or value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value[:2200] if value else None
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, list):
            result = []
            for item in value[:10]:
                cleaned = self.compact_value(item, depth + 1)
                if cleaned not in (None, "", [], {}):
                    result.append(cleaned)
            return result
        if isinstance(value, dict):
            ignored = {
                "created_at", "updated_at", "metadata", "dynamic_profile",
                "re_explain_history", "history",
            }
            result = {}
            for key, item in value.items():
                if key in ignored:
                    continue
                cleaned = self.compact_value(item, depth + 1)
                if cleaned not in (None, "", [], {}):
                    result[str(key)] = cleaned
            return result
        return str(value)[:1000]

    def prepare_step_content(self, step: dict) -> str:
        content = step.get("content", {})
        if not isinstance(content, dict):
            content = {"content": content}
        compact = self.compact_value(content) or {}
        serialized = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return serialized[: self.MAX_STEP_CONTENT_CHARS]

    @staticmethod
    def _finite_number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def normalize_graph(self, value: Any) -> dict | None:
        """قبول بيانات رسم رقمية فقط، دون كود مولّد أو HTML."""
        if not isinstance(value, dict) or value.get("required") is not True:
            return None

        raw_series = value.get("series")
        if not isinstance(raw_series, list):
            return None

        series = []
        for series_index, raw_serie in enumerate(raw_series[: self.MAX_GRAPH_SERIES]):
            if not isinstance(raw_serie, dict):
                continue

            raw_points = raw_serie.get("data")
            if not isinstance(raw_points, list):
                continue

            points = []
            for raw_point in raw_points[: self.MAX_GRAPH_POINTS]:
                if not isinstance(raw_point, dict):
                    continue

                x = self._finite_number(raw_point.get("x", raw_point.get("n")))
                y = self._finite_number(raw_point.get("y", raw_point.get("value")))
                if x is None or y is None:
                    continue

                point = {"x": x, "y": y}
                n = raw_point.get("n")
                if isinstance(n, int) and n >= 0:
                    point["n"] = n

                label = self.normalize_text(raw_point.get("label"))[:40]
                if label:
                    point["label"] = label
                points.append(point)

            if points:
                series.append({
                    "id": self.normalize_text(
                        raw_serie.get("id"), f"series_{series_index + 1}"
                    )[:50],
                    "label": self.normalize_text(raw_serie.get("label"))[:80],
                    "type": "line" if raw_serie.get("type") == "line" else "points",
                    "data": points,
                })

        if not series:
            return None

        all_x = [point["x"] for serie in series for point in serie["data"]]
        all_y = [point["y"] for serie in series for point in serie["data"]]

        x_span = max(all_x) - min(all_x)
        y_span = max(all_y) - min(all_y)
        x_pad = max(x_span * 0.08, 1.0)
        y_pad = max(y_span * 0.10, 1.0)

        return {
            "title": self.normalize_text(value.get("title"), "الرسم البياني")[:120],
            "x_label": self.normalize_text(value.get("x_label"), "x")[:40],
            "y_label": self.normalize_text(value.get("y_label"), "y")[:40],
            "x_domain": [min(all_x) - x_pad, max(all_x) + x_pad],
            "y_domain": [min(all_y) - y_pad, max(all_y) + y_pad],
            "series": series,
            "annotations": [],
            "settings": {
                "connect_points": bool(value.get("connect_points", True)),
                "show_point_labels": bool(value.get("show_point_labels", False)),
                "show_grid": True,
            },
        }

    def normalize_answer(self, raw: Any, request_type: RequestType) -> dict:
        if not isinstance(raw, dict):
            raw = {"content": raw}

        # توافق مع إجابات الإصدارات السابقة.
        if request_type == "example":
            fallback_fields = (
                raw.get("example"),
                raw.get("content"),
                raw.get("explanation"),
                raw.get("simple_explanation"),
            )
        else:
            fallback_fields = (
                raw.get("content"),
                raw.get("explanation"),
                raw.get("simple_explanation"),
                raw.get("direct_answer"),
            )

        content = next(
            (self.normalize_text(value) for value in fallback_fields if self.normalize_text(value)),
            "",
        )[: self.MAX_CONTENT_CHARS]

        if not content:
            return self.fallback_answer(request_type)

        return {
            "type": request_type,
            "content": content,
            "graph": self.normalize_graph(raw.get("graph")),
        }

    def build_prompt(
        self,
        step: dict,
        student_question: str,
        request_type: RequestType,
    ) -> str:
        title = self.normalize_text(step.get("title"), "مرحلة من الدرس")
        step_type = self.normalize_text(step.get("type"), "lesson_step")
        content = self.prepare_step_content(step)
        question = self.normalize_text(student_question)[: self.MAX_STUDENT_QUESTION_CHARS]

        if request_type == "example":
            task = """
أنشئ مثالًا واحدًا فقط يساعد التلميذ على فهم المرحلة.
- ابدأ بمعطيات المثال بوضوح.
- طبّق فكرة المرحلة خطوة بخطوة داخل فقرة مرتبة وسهلة.
- اشرح سبب كل عملية حسابية باختصار.
- اختم بنتيجة المثال.
- لا تعِد شرح الدرس كاملًا ولا تضف قسم شرح منفصل.
""".strip()
        else:
            task = """
أعد شرح المرحلة بطريقة أبسط بكثير وبالتفصيل الكافي لتلميذ لم يفهمها.
- ابدأ من الفكرة الأساسية دون افتراض أنه فهم المصطلحات.
- فسّر الرموز والمعنى الرياضي الضروريين داخل الشرح.
- اربط الأفكار تدريجيًا باستعمال جمل قصيرة وواضحة.
- اشرح لماذا نقوم بكل خطوة، وليس ماذا نفعل فقط.
- لا تعط مثالًا مستقلًا؛ المطلوب هنا شرح المرحلة فقط.
""".strip()

        return f"""
أنت أستاذ رياضيات جزائري متخصص في شرح دروس البكالوريا.
اعتمد حصريًا على المرحلة الحالية، ولا تنتقل إلى مرحلة أخرى أو إلى الدرس كاملًا.

عنوان المرحلة: {title}
نوع المرحلة: {step_type}
محتوى المرحلة: {content}
اختيار التلميذ: {question}
نوع الاستجابة المطلوب: {request_type}

المهمة:
{task}

قواعد إلزامية:
1. أرجع JSON صحيحًا فقط دون Markdown أو نص قبل JSON أو بعده.
2. الحقول المسموحة فقط هي: type وcontent وgraph.
3. type يجب أن يساوي حرفيًا: {request_type}
4. content هو النص الكامل المطلوب، بلغة عربية بسيطة وواضحة.
5. استعمل LaTeX بين \\( و \\) للرموز والتعابير الرياضية.
6. راجع جميع الحسابات والرموز قبل الإرجاع.
7. لا تخترع معطيات تناقض محتوى المرحلة.
8. graph=null افتراضيًا.
9. أضف الرسم فقط إذا كان ضروريًا فعلًا للفهم، مثل منحنى دالة، تمثيل حدود متتالية، مخطط السلم، أو قراءة بيانية.
10. لا ترسم لمجرد وجود أعداد أو صيغة جبرية قابلة للفهم دون رسم.
11. الرسم يحتوي نقاطًا رقمية فقط؛ ممنوع JavaScript أو Python أو HTML.
12. لا تتجاوز سلسلتين و30 نقطة لكل سلسلة.

الشكل العادي:
{{
  "type": "{request_type}",
  "content": "النص المطلوب",
  "graph": null
}}

شكل الرسم عند الضرورة فقط:
{{
  "type": "{request_type}",
  "content": "النص المطلوب مع الإشارة إلى الرسم",
  "graph": {{
    "required": true,
    "title": "عنوان الرسم",
    "x_label": "n",
    "y_label": "u_n",
    "connect_points": true,
    "show_point_labels": true,
    "series": [
      {{
        "id": "u",
        "label": "u_n",
        "type": "points",
        "data": [
          {{"n": 0, "x": 0, "y": 2, "label": "u_0"}}
        ]
      }}
    ]
  }}
}}
""".strip()

    @staticmethod
    def build_context(prompt: str) -> BuiltContext:
        values = {
            "question": "نفّذ نوع المساعدة المحدد للمرحلة الحالية فقط.",
            "intent": "re_explain_step",
            "context_text": prompt,
            "context": prompt,
            "items": [],
            "sources": [],
            "metadata": {},
        }
        try:
            signature = inspect.signature(BuiltContext)
            accepted = {
                name
                for name, parameter in signature.parameters.items()
                if name != "self"
                and parameter.kind
                in {
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                }
            }
            return BuiltContext(**{key: value for key, value in values.items() if key in accepted})
        except (TypeError, ValueError):
            return BuiltContext(
                question=values["question"],
                intent=values["intent"],
                context_text=prompt,
            )

    def generate(
        self,
        step: dict,
        student_question: str,
        request_type: RequestType,
    ) -> dict:
        if not isinstance(step, dict):
            raise ValueError("بيانات المرحلة غير صحيحة.")

        step_id = self.normalize_text(step.get("id"))
        if not step_id:
            raise ValueError("معرف المرحلة غير موجود.")

        request_type = self.normalize_text(request_type).lower()
        if request_type not in self.ALLOWED_REQUEST_TYPES:
            raise ValueError("نوع المساعدة غير صالح.")

        step_title = self.normalize_text(step.get("title"), "مرحلة من الدرس")
        question = self.normalize_text(student_question)
        if not question:
            raise ValueError("طلب المساعدة فارغ.")

        prompt = self.build_prompt(
            step=step,
            student_question=question,
            request_type=request_type,
        )
        generated = self.generator.generate(self.build_context(prompt))

        raw_answer = getattr(generated, "answer", "")
        model = self.normalize_text(getattr(generated, "model", ""))
        parsed = self.extract_json(raw_answer, request_type)

        return {
            "mode": "re_explain_step",
            "step_id": step_id,
            "step_title": step_title,
            "model": model,
            "answer": self.normalize_answer(parsed, request_type),
        }
