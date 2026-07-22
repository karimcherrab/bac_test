import os
import json
from dataclasses import dataclass, field
from typing import Optional

from groq import Groq

from course.models import Axis


@dataclass
class AxisClassifyResult:
    tag: str
    confidence: float
    reason: str


@dataclass
class AxisRetrieveResult:
    axis: Optional[Axis]
    lesson: Optional[Axis] = None
    questions: list[Axis] = field(default_factory=list)
    classification: Optional[AxisClassifyResult] = None


class AxisClassifier:
    def __init__(self, model: str = "openai/gpt-oss-120b"):
        api_key = os.getenv(
            "API_KEY"
        )
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing")

        self.client = Groq(api_key=api_key)
        self.model = model

    def classify(
        self,
        question: str,
        chapter_code: str = "sequences",
    ) -> AxisClassifyResult:

        axes = Axis.objects.filter(
            chapter__code=chapter_code
        ).order_by("order", "id")

        axes_text = "\n".join(
            [
                f"- tag: {axis.tag}\n  title: {axis.title}"
                for axis in axes
            ]
        )

        system_prompt = f"""
أنت مصنف محاور لدروس الرياضيات في البكالوريا الجزائرية.

مهمتك:
تحديد المحور المناسب لسؤال الطالب.

يجب أن تختار tag واحد فقط من القائمة التالية:

{axes_text}

قواعد مهمة:
- لا تختر tag غير موجود في القائمة.
- إذا كان السؤال عن البرهان بالتراجع اختر محور التراجع.
- إذا كان السؤال عن الحصر أو المحدودية اختر محور المتتاليات المحدودة.
- إذا كان السؤال عن النهاية أو التقارب اختر محور النهايات.
- إذا كان السؤال عن متتالية حسابية أو هندسية أو الحد العام اختر محور التعريف والحسابية والهندسية.
- إذا كان السؤال عن u_n+1 = f(u_n) أو التمثيل البياني أو الرسم اختر محور المتتالية التراجعية.
- إذا كان السؤال غير واضح اختر أقرب محور.

أجب فقط JSON صحيح بهذا الشكل:
{{
  "tag": "seq_bounded",
  "confidence": 0.95,
  "reason": "السؤال يتحدث عن محدودية المتتالية."
}}
"""

        user_prompt = f"""
سؤال الطالب:

{question}

حدد tag المناسب.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()},
                ],
                temperature=0,
            )

            content = response.choices[0].message.content.strip()
            data = json.loads(content)

            tag = data.get("tag", "")
            confidence = float(data.get("confidence", 0))
            reason = data.get("reason", "")

            valid_tags = set(axes.values_list("tag", flat=True))

            if tag not in valid_tags:
                return AxisClassifyResult(
                    tag="",
                    confidence=0,
                    reason="AI returned invalid tag",
                )

            return AxisClassifyResult(
                tag=tag,
                confidence=confidence,
                reason=reason,
            )

        except Exception as e:
            return AxisClassifyResult(
                tag="",
                confidence=0,
                reason=f"Axis classification failed: {str(e)}",
            )


class AxisRetriever:
    def __init__(self, classifier: Optional[AxisClassifier] = None):
        self.classifier = classifier or AxisClassifier()

    def retrieve(
        self,
        question: str = "",
        tag: str | None = None,
        chapter_code: str = "sequences",
        questions_limit: int = 20,
    ) -> AxisRetrieveResult:

        classification = None

        if tag:
            axis = Axis.objects.filter(
                tag=tag,
                chapter__code=chapter_code
            ).first()
        else:
            classification = self.classifier.classify(
                question=question,
                chapter_code=chapter_code,
            )

            if not classification.tag:
                return AxisRetrieveResult(
                    axis=None,
                    classification=classification,
                )

            axis = Axis.objects.filter(
                tag=classification.tag,
                chapter__code=chapter_code,
            ).first()

        if axis is None:
            return AxisRetrieveResult(
                axis=None,
                classification=classification,
            )

        lesson = Axis.objects.filter(
            axis=axis,
            item_type="lesson",
        ).first()

        questions = list(
            Axis.objects.filter(
                axis=axis,
                item_type="bac_question",
            )
            .order_by("year", "exercise_title", "question_number")[
                :questions_limit
            ]
        )

        return AxisRetrieveResult(
            axis=axis,
            lesson=lesson,
            questions=questions,
            classification=classification,
        )