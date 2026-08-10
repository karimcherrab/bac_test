from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from groq import Groq

logger = logging.getLogger(__name__)


class SimpleQuestionSolutionError(Exception):
    """خطأ عام أثناء إنشاء الحل المبسط."""


class SimpleQuestionSolutionParsingError(SimpleQuestionSolutionError):
    """إجابة النموذج ليست JSON صالحًا أو ناقصة."""


@dataclass
class SimpleQuestionSolutionResult:
    solution: dict[str, Any]
    model_name: str
    raw_response: dict[str, Any]


class SimpleQuestionSolutionService:
    """
    ينشئ حلاً جديدًا شديد التبسيط لسؤال Question موجود في قاعدة البيانات.

    المصدر الوحيد للحقيقة هو Question القادم من Django:
    - نص السؤال.
    - السياق / standalone_support.
    - graph_data.
    - الحل النموذجي المحفوظ (إن وجد) كمرجع للتأكد من النتيجة.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"
    MAX_SOLUTION_CHARS = 9000
    MAX_CONTEXT_CHARS = 4500
    MAX_SUPPORT_ITEMS = 8
    MAX_GRAPH_POINTS = 16

    def __init__(self, model_name: str | None = None):
        api_key = os.getenv("API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise SimpleQuestionSolutionError(
                "API_KEY أو GROQ_API_KEY غير موجود في متغيرات البيئة."
            )

        self.client = Groq(api_key=api_key)
        self.model_name = (
            model_name
            or os.getenv("GROQ_SIMPLE_SOLUTION_MODEL")
            or os.getenv("GROQ_EXERCISE_MODEL")
            or self.DEFAULT_MODEL
        )

    def generate(self, *, question) -> SimpleQuestionSolutionResult:
        subject_kind = self._subject_kind(question)
        prompt = self._build_prompt(question=question, subject_kind=subject_kind)

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                temperature=0.06,
                max_tokens=4300,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt(subject_kind),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )
        except Exception as exc:
            logger.exception("Simple question solution generation failed")
            raise SimpleQuestionSolutionError(
                f"فشل الاتصال بنموذج الذكاء الاصطناعي: {exc}"
            ) from exc

        content = completion.choices[0].message.content or ""
        parsed = self._parse(content)
        normalized = self._normalize_solution(parsed)

        return SimpleQuestionSolutionResult(
            solution=normalized,
            model_name=self.model_name,
            raw_response=parsed,
        )

    @staticmethod
    def _subject_kind(question) -> str:
        subject = getattr(
            getattr(getattr(question, "axis", None), "chapter", None),
            "subject",
            None,
        )
        code = str(getattr(subject, "code", "") or "").lower()
        name = str(getattr(subject, "name", "") or "").lower()
        value = f"{code} {name}"

        if any(word in value for word in ("phys", "physics", "فيزياء", "physique")):
            return "physics"
        if any(word in value for word in ("math", "رياضيات", "mathématique", "mathematique")):
            return "math"
        return "general"

    @staticmethod
    def _system_prompt(subject_kind: str) -> str:
        role = {
            "physics": "أنت أستاذ فيزياء جزائري ممتاز لتلاميذ السنة الثالثة ثانوي والبكالوريا.",
            "math": "أنت أستاذ رياضيات جزائري ممتاز لتلاميذ السنة الثالثة ثانوي والبكالوريا.",
            "general": "أنت أستاذ جزائري ممتاز لتلاميذ السنة الثالثة ثانوي والبكالوريا.",
        }[subject_kind]

        return f"""
{role}

مهمتك ليست تلخيص الحل الموجود، بل إعادة حل نفس السؤال بطريقة أبسط جدًا جدًا لتلميذ لم يفهم التصحيح النموذجي.

قواعد إلزامية:
1. لا تغيّر السؤال ولا المعطيات ولا المطلوب.
2. إذا وُجد حل نموذجي محفوظ فاعتبر نتائجه مرجعًا للتحقق من صحة جوابك، ولا تناقض النتيجة الصحيحة.
3. اشرح كأن التلميذ ضعيف جدًا: فكرة واحدة صغيرة في كل خطوة.
4. قبل أي قانون قل للتلميذ لماذا نحتاجه.
5. لا تقفز بين عمليتين حسابيتين مهمتين.
6. لا تستعمل مفاهيم خارج مستوى السنة الثالثة ثانوي.
7. استعمل العربية البسيطة جدًا والجمل القصيرة.
8. الرياضيات والفيزياء داخل $...$ فقط.
9. وحدات الفيزياء تكتب LaTeX مثل $20\\,\\text{{V}}$ و $0.2\\,\\text{{A}}$.
10. لا تستعمل Markdown، ولا ```، ولا عناوين #.
11. أعد JSON صالحًا فقط.
12. إذا كان الرسم ضروريًا، اشرح كيف نقرأ القيمة من الرسم، لكن لا تخترع قيمًا غير موجودة في بيانات السؤال.
13. لا تجعل الشرح طويلًا لمجرد الطول؛ الهدف أن يفهم التلميذ كل انتقال.
""".strip()

    def _build_prompt(self, *, question, subject_kind: str) -> str:
        subject = question.axis.chapter.subject
        question_text = (
            str(getattr(question, "standalone_text", "") or "").strip()
            or str(getattr(question, "text", "") or "").strip()
        )

        payload = {
            "question_id": question.id,
            "code": question.code,
            "title": question.title,
            "number": question.number,
            "year": question.year,
            "difficulty": question.difficulty,
            "skill": question.skill,
            "axis": {
                "id": question.axis_id,
                "tag": question.axis.tag,
                "title": question.axis.title,
            },
            "chapter": {
                "id": question.axis.chapter_id,
                "code": question.axis.chapter.code,
                "title": question.axis.chapter.title,
            },
            "subject": {
                "id": subject.id,
                "code": subject.code,
                "name": subject.name,
                "kind": subject_kind,
            },
            "question_text": question_text,
            "context": self._short_text(question.context, self.MAX_CONTEXT_CHARS),
            "standalone_support": self._compact_support(question.standalone_support),
            "graph": self._compact_graph(question.graph_data),
            "reference_solution": self._compact_solution(question.solution),
        }

        output_schema = {
            "simple_solution": {
                "teacher_intro": "جملة قصيرة تطمئن التلميذ وتوضح ما سنفعله دون كلام زائد",
                "what_is_given": [
                    {"label": "المعطى", "value": "$...$", "meaning": "ماذا يعني ببساطة"}
                ],
                "what_is_required": "ما الذي يريد السؤال إيجاده بكلمات بسيطة",
                "idea": "الفكرة الأساسية للحل في جملة أو جملتين",
                "steps": [
                    {
                        "order": 1,
                        "title": "عنوان قصير",
                        "explanation": "ماذا نفعل ولماذا بلغة بسيطة جدًا",
                        "formula": "$...$",
                        "calculation": "$...$",
                        "result": "$...$",
                    }
                ],
                "final_answer": "الجواب النهائي كاملًا",
                "verification": "تحقق بسيط جدًا إن كان مناسبًا",
                "memory_tip": "قاعدة صغيرة يتذكرها التلميذ في تمرين مشابه",
            }
        }

        return (
            "حل السؤال التالي من جديد بأبسط طريقة ممكنة.\n"
            "لا تشرح التصحيح النموذجي كلمة بكلمة؛ ابنِ حلاً تعليميًا جديدًا، "
            "واستعمل التصحيح المخزن فقط لضمان صحة النتائج.\n\n"
            f"بيانات السؤال:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'), default=str)}\n\n"
            "البنية المطلوبة حرفيًا:\n"
            f"{json.dumps(output_schema, ensure_ascii=False, separators=(',', ':'))}\n\n"
            "أعد JSON فقط."
        )

    @staticmethod
    def _short_text(value: Any, limit: int) -> str:
        text = str(value or "").strip()
        return text if len(text) <= limit else text[:limit].rstrip() + "..."

    def _compact_support(self, value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value[: self.MAX_SUPPORT_ITEMS]:
            if isinstance(item, dict):
                compact = {}
                for key in (
                    "title", "text", "content", "previous_results",
                    "preliminary_results_to_prove", "values", "table",
                ):
                    if key in item:
                        compact[key] = item[key]
                result.append(compact or item)
            else:
                result.append(item)
        return result

    def _compact_solution(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or not value:
            return {}

        allowed_keys = (
            "strategy", "detailed_explanation", "explanation", "steps",
            "solution_steps", "final_answer", "verification", "result",
            "answer", "simple_solution",
        )
        compact = {key: value[key] for key in allowed_keys if key in value}
        serialized = json.dumps(compact, ensure_ascii=False, default=str)
        if len(serialized) <= self.MAX_SOLUTION_CHARS:
            return compact

        return {
            "final_answer": value.get("final_answer") or value.get("answer") or "",
            "strategy": self._short_text(value.get("strategy"), 1200),
            "detailed_explanation": self._short_text(
                value.get("detailed_explanation") or value.get("explanation"),
                2500,
            ),
            "steps": (value.get("steps") or value.get("solution_steps") or [])[:8],
        }

    def _compact_graph(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or not value:
            return {}

        graph = {
            key: value.get(key)
            for key in (
                "graph_type", "title", "x_label", "y_label", "x_domain",
                "y_domain", "axes", "viewport", "annotations",
                "solution_annotations", "sequence_values", "react_data",
            )
            if value.get(key) not in (None, "", [], {})
        }

        functions = value.get("functions")
        if isinstance(functions, list):
            compact_functions = []
            for function in functions[:3]:
                if not isinstance(function, dict):
                    continue
                points = function.get("points") or function.get("data") or []
                if isinstance(points, list) and len(points) > self.MAX_GRAPH_POINTS:
                    step = max(1, len(points) // self.MAX_GRAPH_POINTS)
                    points = points[::step][: self.MAX_GRAPH_POINTS]
                compact_functions.append({
                    "id": function.get("id"),
                    "label": function.get("label"),
                    "expression": function.get("expression"),
                    "points": points if isinstance(points, list) else [],
                })
            graph["functions"] = compact_functions

        # react_data قد يكون كبيرًا جدًا. نحتفظ بعينة من series فقط.
        react_data = graph.get("react_data")
        if isinstance(react_data, dict):
            safe_react = {k: react_data.get(k) for k in ("title", "axes", "annotations") if react_data.get(k)}
            safe_series = []
            for series in react_data.get("series", [])[:3] if isinstance(react_data.get("series"), list) else []:
                if not isinstance(series, dict):
                    continue
                data = series.get("data", [])
                if isinstance(data, list) and len(data) > self.MAX_GRAPH_POINTS:
                    step = max(1, len(data) // self.MAX_GRAPH_POINTS)
                    data = data[::step][: self.MAX_GRAPH_POINTS]
                safe_series.append({
                    "id": series.get("id"),
                    "label": series.get("label"),
                    "type": series.get("type"),
                    "data": data,
                })
            if safe_series:
                safe_react["series"] = safe_series
            graph["react_data"] = safe_react

        return graph

    @staticmethod
    def _parse(content: str) -> dict[str, Any]:
        text = str(content or "").strip()
        if not text:
            raise SimpleQuestionSolutionParsingError("إجابة النموذج فارغة.")

        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end <= start:
                raise SimpleQuestionSolutionParsingError("إجابة النموذج ليست JSON صالحًا.")
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise SimpleQuestionSolutionParsingError(
                    f"تعذر قراءة JSON الناتج: {exc}"
                ) from exc

        if not isinstance(parsed, dict):
            raise SimpleQuestionSolutionParsingError("الإجابة يجب أن تكون JSON object.")
        return parsed

    def _normalize_solution(self, parsed: dict[str, Any]) -> dict[str, Any]:
        raw = parsed.get("simple_solution")
        if not isinstance(raw, dict):
            raw = parsed.get("solution") if isinstance(parsed.get("solution"), dict) else parsed

        teacher_intro = self._clean(raw.get("teacher_intro") or raw.get("intro"))
        what_is_required = self._clean(raw.get("what_is_required"))
        idea = self._clean(raw.get("idea"))
        final_answer = self._clean(raw.get("final_answer") or raw.get("answer"))
        verification = self._clean(raw.get("verification"))
        memory_tip = self._clean(raw.get("memory_tip"))

        given = []
        for item in raw.get("what_is_given", []) if isinstance(raw.get("what_is_given"), list) else []:
            if isinstance(item, dict):
                label = self._clean(item.get("label"))
                value = self._clean(item.get("value"))
                meaning = self._clean(item.get("meaning"))
                if label or value or meaning:
                    given.append({"label": label, "value": value, "meaning": meaning})
            else:
                text = self._clean(item)
                if text:
                    given.append({"label": "", "value": text, "meaning": ""})

        steps = []
        raw_steps = raw.get("steps") or raw.get("solution_steps") or []
        if isinstance(raw_steps, list):
            for index, step in enumerate(raw_steps[:20], start=1):
                if not isinstance(step, dict):
                    continue
                normalized = {
                    "order": index,
                    "title": self._clean(step.get("title")) or f"الخطوة {index}",
                    "explanation": self._clean(step.get("explanation") or step.get("description")),
                    "formula": self._clean(step.get("formula")),
                    "calculation": self._clean(step.get("calculation") or step.get("math")),
                    "result": self._clean(step.get("result") or step.get("conclusion")),
                }
                if any(normalized[key] for key in ("explanation", "formula", "calculation", "result")):
                    steps.append(normalized)

        if not steps:
            raise SimpleQuestionSolutionParsingError("الحل المبسط لا يحتوي على خطوات صالحة.")
        if not final_answer:
            raise SimpleQuestionSolutionParsingError("الحل المبسط لا يحتوي على جواب نهائي.")

        return {
            "teacher_intro": teacher_intro or "سنحل هذا السؤال بهدوء، خطوة صغيرة في كل مرة.",
            "what_is_given": given,
            "what_is_required": what_is_required,
            "idea": idea,
            "steps": steps,
            "final_answer": final_answer,
            "verification": verification,
            "memory_tip": memory_tip,
        }

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()
