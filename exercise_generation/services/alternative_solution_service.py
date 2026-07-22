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
    pass


class AlternativeSolutionParsingError(AlternativeSolutionGenerationError):
    pass


@dataclass
class GeneratedAlternativeSolutionData:
    explanation: str
    solution_steps: list[dict[str, Any]]
    final_answer: str
    model_name: str
    raw_response: dict[str, Any]


class AlternativeSolutionService:
    def __init__(self, model_name: str | None = None):
        api_key = os.getenv(
            "API_KEY"
        )
        if not api_key:
            raise AlternativeSolutionGenerationError(
                "GROQ_API_KEY غير موجود في متغيرات البيئة."
            )

        self.client = Groq(api_key=api_key)
        self.model_name = model_name or os.getenv(
            "GROQ_EXERCISE_MODEL",
            "openai/gpt-oss-120b",
        )

    def generate_and_save(
        self,
        *,
        exercise: GeneratedExercise,
        student,
        simplification_level: str = "very_simple",
    ) -> GeneratedExerciseAlternativeSolution:
        generated = self.generate(
            exercise=exercise,
            simplification_level=simplification_level,
        )
        with transaction.atomic():
            return GeneratedExerciseAlternativeSolution.objects.create(
                exercise=exercise,
                student=student,
                explanation=generated.explanation,
                solution_steps=generated.solution_steps,
                final_answer=generated.final_answer,
                model_name=generated.model_name,
                raw_ai_response=generated.raw_response,
            )

    def generate(
        self,
        *,
        exercise: GeneratedExercise,
        simplification_level: str = "very_simple",
    ) -> GeneratedAlternativeSolutionData:
        if not exercise.solution_steps or not exercise.final_answer:
            raise AlternativeSolutionGenerationError(
                "التمرين لا يحتوي على حل أول كامل."
            )

        prompt = self._prompt(exercise, simplification_level)
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                temperature=0.08,
                max_tokens=3600,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            raise AlternativeSolutionGenerationError(
                f"فشل الاتصال بالنموذج: {exc}"
            ) from exc

        parsed = self._parse(completion.choices[0].message.content or "")
        return GeneratedAlternativeSolutionData(
            explanation=parsed["explanation"],
            solution_steps=parsed["solution_steps"],
            final_answer=parsed["final_answer"],
            model_name=self.model_name,
            raw_response=parsed,
        )

    @staticmethod
    def _system_prompt() -> str:
        return """
أنت أستاذ رياضيات جزائري. أنشئ حلًا بديلًا أبسط للسؤال نفسه.
لا تغير السؤال ولا النتائج الصحيحة. اشرح كل عملية ولماذا نستعملها.
لا يوجد عدد ثابت للخطوات؛ استخدم العدد الضروري فقط لإعطاء حل كامل ومفهوم.
حل كل المطالب، ولا تستعمل Markdown. أعد JSON صالحًا فقط بالبنية:
{
  "explanation": "فكرة الحل المبسط",
  "solution_steps": [
    {
      "step_number": 1,
      "title": "",
      "explanation": "",
      "calculation": "",
      "result": ""
    }
  ],
  "final_answer": "جواب جميع المطالب"
}
""".strip()

    @staticmethod
    def _prompt(exercise: GeneratedExercise, level: str) -> str:
        instruction = (
            "اشرح كأن التلميذ ضعيف جدًا، وفسّر كل قاعدة وعملية."
            if level == "very_simple"
            else "اشرح بطريقة بسيطة وواضحة."
        )
        return f"""
العنوان: {exercise.title}
السؤال: {exercise.question}
المهارة: {exercise.skill or 'غير محددة'}
الحل الأول: {json.dumps(exercise.solution_steps, ensure_ascii=False)}
الجواب الأول: {exercise.final_answer}
مستوى التبسيط: {instruction}

حل جميع أجزاء السؤال، وحافظ على النتائج الصحيحة، ولا تختصر الانتقالات المهمة.
""".strip()

    def _parse(self, content: str) -> dict[str, Any]:
        if not content.strip():
            raise AlternativeSolutionParsingError("إجابة النموذج فارغة.")

        cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AlternativeSolutionParsingError(f"JSON غير صالح: {exc}") from exc

        if not isinstance(data, dict):
            raise AlternativeSolutionParsingError("الحل يجب أن يكون JSON object.")

        explanation = str(data.get("explanation") or "").strip()
        final_answer = str(data.get("final_answer") or "").strip()
        raw_steps = data.get("solution_steps")
        if not explanation or not final_answer or not isinstance(raw_steps, list):
            raise AlternativeSolutionParsingError("الحل البديل غير مكتمل.")

        steps = []
        for index, step in enumerate(raw_steps, start=1):
            if not isinstance(step, dict):
                continue
            step_explanation = str(step.get("explanation") or "").strip()
            calculation = str(step.get("calculation") or "").strip()
            result = str(step.get("result") or "").strip()
            if step_explanation and (calculation or result):
                steps.append(
                    {
                        "step_number": index,
                        "title": str(step.get("title") or f"الخطوة {index}").strip(),
                        "explanation": step_explanation,
                        "calculation": calculation,
                        "result": result,
                    }
                )

        if len(steps) < 2:
            raise AlternativeSolutionParsingError("الحل البديل مختصر جدًا.")

        return {
            "explanation": explanation,
            "solution_steps": steps[:30],
            "final_answer": final_answer,
        }
