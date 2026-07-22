# knowledge/retrieval/context_builder.py

import json
from dataclasses import dataclass, field
from typing import Any

from course.models import Axis

from knowledge.retrieval.chapter_retriever import (
    ChapterRetrieveResult,
)


@dataclass
class BuiltContext:
    question: str
    intent: str
    context_text: str
    selected_axis: Axis | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)


class ContextBuilder:
    def build(
        self,
        question: str,
        intent: str,
        retrieval: ChapterRetrieveResult,
        max_axis_chars: int = 10000,
        max_exercise_chars: int = 2500,
    ) -> BuiltContext:

        sections: list[str] = []
        sources: list[dict[str, Any]] = []

        chapter = retrieval.chapter
        selected_axis = retrieval.selected_axis

        sections.append(
            f"""
# الفصل الحالي

معرف الفصل: {chapter.id}
عنوان الفصل: {chapter.title}
رمز الفصل: {chapter.code}
""".strip()
        )

        sections.append(
            f"""
# سؤال الطالب

{question}

# نوع الطلب

{intent}
""".strip()
        )

        if selected_axis:
            axis_content = self.to_text(
                selected_axis.content
            )

            axis_content = self.truncate(
                axis_content,
                max_axis_chars,
            )

            sections.append(
                f"""
# المحور الأكثر ارتباطًا بالسؤال

معرف المحور: {selected_axis.id}
رمز المحور: {selected_axis.tag}
عنوان المحور: {selected_axis.title}

# محتوى الدرس

{axis_content}
""".strip()
            )

            sources.append({
                "type": "axis",
                "id": selected_axis.id,
                "tag": selected_axis.tag,
                "title": selected_axis.title,
            })

        else:
            sections.append(
                """
# المحور

لم يتم تحديد محور دقيق.
استعمل عناوين المحاور الموجودة داخل الفصل فقط لفهم سؤال الطالب.
""".strip()
            )

            axis_titles = "\n".join(
                f"- {axis.title} ({axis.tag})"
                for axis in retrieval.axes
            )

            sections.append(
                f"""
# محاور الفصل

{axis_titles}
""".strip()
            )

        if retrieval.exercises:
            exercise_sections = []

            for index, exercise in enumerate(
                retrieval.exercises,
                start=1,
            ):
                exercise_content = self.to_text(
                    getattr(exercise, "content", {})
                )

                exercise_content = self.truncate(
                    exercise_content,
                    max_exercise_chars,
                )

                exercise_sections.append(
                    f"""
## تمرين مرجعي {index}

السنة: {getattr(exercise, "year", "")}
رقم التمرين: {getattr(exercise, "exercise_number", "")}
العنوان: {getattr(exercise, "title", "")}

المحتوى:
{exercise_content}
""".strip()
                )

                sources.append({
                    "type": "bac_exercise",
                    "id": exercise.id,
                    "year": getattr(exercise, "year", None),
                    "title": getattr(exercise, "title", ""),
                })

            sections.append(
                "# تمارين مرجعية من نفس الفصل\n\n"
                + "\n\n".join(exercise_sections)
            )

        sections.append(
            """
# قواعد الإجابة

- أجب عن سؤال الطالب داخل الفصل الحالي فقط.
- ركز على المحور الأكثر ارتباطًا بالسؤال.
- تمارين البكالوريا مراجع مساعدة وليست نصًا يجب نسخه.
- لا تعط حل تمرين كامل إلا إذا طلب الطالب الحل.
- إذا لم توجد معلومات كافية، قل إن المعطيات غير كافية.
""".strip()
        )

        return BuiltContext(
            question=question,
            intent=intent,
            context_text="\n\n".join(sections),
            selected_axis=selected_axis,
            sources=sources,
        )

    @staticmethod
    def to_text(value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value

        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
            )
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text

        return text[:max_chars] + "\n...[تم اختصار المحتوى]"