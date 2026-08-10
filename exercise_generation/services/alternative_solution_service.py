import json
import os
import re
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from groq import Groq

from exercise_generation.models import (
    GeneratedExercise,
    GeneratedExerciseAlternativeSolution,
)


class AlternativeSolutionGenerationError(Exception):
    """خطأ عام أثناء إنشاء الحل البديل."""
    pass


class AlternativeSolutionParsingError(
    AlternativeSolutionGenerationError
):
    """إجابة النموذج غير صالحة أو غير مكتملة."""
    pass


@dataclass
class GeneratedAlternativeSolutionData:
    explanation: str
    solution_steps: list[dict[str, Any]]
    final_answer: str
    model_name: str
    raw_response: dict[str, Any]


class AlternativeSolutionService:
    def __init__(
        self,
        model_name: str | None = None,
    ):
        api_key = os.getenv("API_KEY")

        if not api_key:
            raise AlternativeSolutionGenerationError(
                "API_KEY غير موجود في متغيرات البيئة."
            )

        self.client = Groq(
            api_key=api_key,
        )

        self.model_name = (
            model_name
            or os.getenv(
                "GROQ_EXERCISE_MODEL",
                "openai/gpt-oss-120b",
            )
        )

    def generate_and_save(
        self,
        *,
        exercise: GeneratedExercise,
        student,
        simplification_level: str = "very_simple",
    ) -> GeneratedExerciseAlternativeSolution:
        """
        إنشاء حل بديل ثم حفظه في قاعدة البيانات.
        """

        generated = self.generate(
            exercise=exercise,
            simplification_level=simplification_level,
        )

        with transaction.atomic():
            alternative_solution = (
                GeneratedExerciseAlternativeSolution.objects.create(
                    exercise=exercise,
                    student=student,
                    explanation=generated.explanation,
                    solution_steps=generated.solution_steps,
                    final_answer=generated.final_answer,
                    model_name=generated.model_name,
                    raw_ai_response=generated.raw_response,
                )
            )

        return alternative_solution

    def generate(
        self,
        *,
        exercise: GeneratedExercise,
        simplification_level: str = "very_simple",
    ) -> GeneratedAlternativeSolutionData:
        """
        إنشاء حل بديل أبسط للتمرين.
        """

        if (
            not exercise.solution_steps
            or not exercise.final_answer
        ):
            raise AlternativeSolutionGenerationError(
                "التمرين لا يحتوي على حل أول كامل."
            )

        system_prompt = self._system_prompt(
            exercise
        )

        user_prompt = self._prompt(
            exercise,
            simplification_level,
        )

        try:
            completion = (
                self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=0.08,
                    max_tokens=3600,
                    response_format={
                        "type": "json_object"
                    },
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
                )
            )

        except Exception as exc:
            raise AlternativeSolutionGenerationError(
                f"فشل الاتصال بالنموذج: {exc}"
            ) from exc

        try:
            content = (
                completion
                .choices[0]
                .message
                .content
                or ""
            )
        except (
            AttributeError,
            IndexError,
            TypeError,
        ) as exc:
            raise AlternativeSolutionGenerationError(
                "النموذج لم يرجع إجابة صالحة."
            ) from exc

        parsed = self._parse(
            content
        )

        return GeneratedAlternativeSolutionData(
            explanation=parsed["explanation"],
            solution_steps=parsed["solution_steps"],
            final_answer=parsed["final_answer"],
            model_name=self.model_name,
            raw_response=parsed,
        )

    @staticmethod
    def _system_prompt(
        exercise: GeneratedExercise,
    ) -> str:
        """
        بناء system prompt.

        مهم جدًا:
        بما أننا نستعمل f-string من أجل {role}،
        يجب استعمال {{ و }} عند كتابة JSON داخل النص.
        """

        axis = getattr(
            exercise,
            "axis",
            None,
        )

        chapter = getattr(
            axis,
            "chapter",
            None,
        )

        subject = getattr(
            chapter,
            "subject",
            None,
        )

        subject_code = str(
            getattr(
                subject,
                "code",
                "",
            )
            or ""
        )

        subject_name = str(
            getattr(
                subject,
                "name",
                "",
            )
            or ""
        )

        source = (
            f"{subject_code} {subject_name}"
        ).lower()

        physics_markers = (
            "phys",
            "physics",
            "physique",
            "فيزياء",
        )

        is_physics = any(
            marker in source
            for marker in physics_markers
        )

        role = (
            "أستاذ فيزياء جزائري"
            if is_physics
            else "أستاذ رياضيات جزائري"
        )

        return f"""
أنت {role} خبير في برنامج السنة الثالثة ثانوي والبكالوريا الجزائرية.

مهمتك هي إنشاء حل بديل أبسط للسؤال نفسه.

قواعد إجبارية:

1. لا تغير نص السؤال.

2. لا تغير المعطيات.

3. لا تغير النتائج الصحيحة الموجودة في الحل الأول.

4. الهدف ليس إنشاء طريقة أصعب، بل شرح الحل بطريقة أبسط وأكثر وضوحًا.

5. اشرح للتلميذ لماذا نقوم بكل خطوة.

6. إذا استعملت قانونًا، اذكر القانون ثم طبقه.

7. لا تقفز مباشرة من المعطيات إلى النتيجة.

8. حافظ على جميع الوحدات الفيزيائية والرموز الرياضية الصحيحة.

9. استعمل $...$ لكتابة الصيغ الرياضية والفيزيائية.

10. يجب حل جميع مطالب السؤال.

11. يمكن أن يكون عدد الخطوات 2 أو 3 أو 4 أو أكثر حسب الحاجة.

12. لا تضف خطوات فارغة فقط لزيادة العدد.

13. لا تستعمل Markdown.

14. لا تستعمل ```json.

15. لا تكتب أي نص خارج JSON.

16. يجب أن يكون الرد JSON صالحًا فقط.

البنية المطلوبة حرفيًا:

{{
  "explanation": "شرح مختصر لفكرة الحل المبسط",
  "solution_steps": [
    {{
      "step_number": 1,
      "title": "عنوان واضح للخطوة",
      "explanation": "شرح ما نفعله ولماذا نقوم بهذه الخطوة",
      "calculation": "$العملية الرياضية أو الفيزيائية$",
      "result": "$النتيجة$"
    }},
    {{
      "step_number": 2,
      "title": "عنوان واضح للخطوة",
      "explanation": "شرح الخطوة الثانية",
      "calculation": "$العملية$",
      "result": "$النتيجة$"
    }}
  ],
  "final_answer": "الجواب النهائي لجميع مطالب السؤال"
}}

مهم:

- explanation يجب ألا يكون فارغًا.
- solution_steps يجب أن تحتوي خطوات مفهومة.
- كل خطوة يجب أن تحتوي explanation.
- calculation تحتوي العملية عند وجود عملية حسابية.
- result تحتوي نتيجة الخطوة.
- final_answer يجب أن يحتوي الجواب النهائي الكامل.
""".strip()

    @staticmethod
    def _prompt(
        exercise: GeneratedExercise,
        level: str,
    ) -> str:
        """
        بناء prompt يحتوي السؤال والحل الأصلي.
        """

        if level == "very_simple":
            instruction = (
                "اشرح كأن التلميذ ضعيف جدًا في المادة. "
                "فسّر كل قاعدة وكل انتقال حسابي بطريقة بسيطة جدًا، "
                "ولا تفترض أن التلميذ فهم الخطوات الضمنية."
            )
        else:
            instruction = (
                "اشرح بطريقة بسيطة وواضحة، "
                "مع توضيح الخطوات الأساسية."
            )

        original_steps = json.dumps(
            exercise.solution_steps,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        title = str(
            exercise.title
            or ""
        ).strip()

        question = str(
            exercise.question
            or ""
        ).strip()

        skill = str(
            exercise.skill
            or "غير محددة"
        ).strip()

        final_answer = str(
            exercise.final_answer
            or ""
        ).strip()

        return f"""
العنوان:
{title}

السؤال:
{question}

المهارة:
{skill}

الحل الأصلي الصحيح:
{original_steps}

الجواب النهائي الأصلي:
{final_answer}

مستوى الشرح المطلوب:
{instruction}

أنشئ الآن حلًا بديلًا أبسط.

شروط مهمة:

- حل جميع أجزاء السؤال.
- حافظ على نفس النتائج الصحيحة.
- لا تغير المعطيات.
- لا تضف معلومات غير موجودة في السؤال.
- لا تختصر الانتقالات المهمة.
- فسّر لماذا نستعمل القانون أو العملية.
- اجعل الشرح مناسبًا لتلميذ بكالوريا.
- أعد JSON فقط.
""".strip()

    def _parse(
        self,
        content: str,
    ) -> dict[str, Any]:
        """
        تحويل جواب النموذج إلى JSON وتنظيفه والتحقق منه.
        """

        if not isinstance(
            content,
            str,
        ):
            raise AlternativeSolutionParsingError(
                "إجابة النموذج ليست نصًا."
            )

        content = content.strip()

        if not content:
            raise AlternativeSolutionParsingError(
                "إجابة النموذج فارغة."
            )

        cleaned = self._clean_json_response(
            content
        )

        try:
            data = json.loads(
                cleaned
            )

        except json.JSONDecodeError as exc:
            raise AlternativeSolutionParsingError(
                "JSON غير صالح من النموذج: "
                f"{exc}"
            ) from exc

        if not isinstance(
            data,
            dict,
        ):
            raise AlternativeSolutionParsingError(
                "الحل يجب أن يكون JSON object."
            )

        explanation = self._text(
            data.get(
                "explanation"
            )
        )

        final_answer = self._text(
            data.get(
                "final_answer"
            )
        )

        raw_steps = data.get(
            "solution_steps"
        )

        if not explanation:
            raise AlternativeSolutionParsingError(
                "الحل البديل لا يحتوي على explanation."
            )

        if not final_answer:
            raise AlternativeSolutionParsingError(
                "الحل البديل لا يحتوي على final_answer."
            )

        if not isinstance(
            raw_steps,
            list,
        ):
            raise AlternativeSolutionParsingError(
                "solution_steps يجب أن تكون قائمة."
            )

        steps: list[
            dict[str, Any]
        ] = []

        for index, step in enumerate(
            raw_steps,
            start=1,
        ):
            if not isinstance(
                step,
                dict,
            ):
                continue

            title = self._text(
                step.get(
                    "title"
                )
            )

            step_explanation = self._text(
                step.get(
                    "explanation"
                )
            )

            calculation = self._text(
                step.get(
                    "calculation"
                )
            )

            result = self._text(
                step.get(
                    "result"
                )
            )

            if not step_explanation:
                continue

            if (
                not calculation
                and not result
            ):
                continue

            steps.append(
                {
                    "step_number": index,
                    "title": (
                        title
                        or f"الخطوة {index}"
                    ),
                    "explanation": (
                        step_explanation
                    ),
                    "calculation": (
                        calculation
                    ),
                    "result": result,
                }
            )

        if not steps:
            raise AlternativeSolutionParsingError(
                "الحل البديل لا يحتوي على خطوات صالحة."
            )

        # لا نفرض خطوتين بالضرورة لأن بعض الأسئلة
        # قد يكون حلها الصحيح في خطوة واحدة فقط.
        steps = steps[:30]

        return {
            "explanation": explanation,
            "solution_steps": steps,
            "final_answer": final_answer,
        }

    @staticmethod
    def _clean_json_response(
        content: str,
    ) -> str:
        """
        تنظيف الحالات التي يرسل فيها النموذج
        ```json ... ```
        أو نصًا قبل/بعد JSON.
        """

        cleaned = content.strip()

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

        cleaned = cleaned.strip()

        # إذا كان هناك نص إضافي قبل JSON أو بعده
        # نحاول استخراج أول object كامل.
        if not cleaned.startswith("{"):
            start = cleaned.find("{")

            if start != -1:
                cleaned = cleaned[start:]

        if not cleaned.endswith("}"):
            end = cleaned.rfind("}")

            if end != -1:
                cleaned = cleaned[: end + 1]

        return cleaned.strip()

    @staticmethod
    def _text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        if isinstance(
            value,
            (
                int,
                float,
                bool,
            ),
        ):
            return str(
                value
            ).strip()

        return str(
            value
        ).strip()