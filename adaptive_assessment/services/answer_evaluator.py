import json
import os

from django.conf import settings

from adaptive_assessment.schemas import GRADING_JSON_SCHEMA
from adaptive_assessment.services.groq_resilience import call_with_retries, is_rate_limit_error

try:
    import groq
    Groq = groq.Groq
except ImportError:  # pragma: no cover
    groq = None
    Groq = None


class AnswerEvaluationError(RuntimeError):
    pass


class TeacherAnswerEvaluator:
    """AI teacher with rate-limit-safe, structured, step-by-step grading."""

    def __init__(self):
        if Groq is None:
            raise AnswerEvaluationError("Install the Groq SDK: pip install -U groq")

        api_key = (
            getattr(settings, "GROQ_API_KEY", "")
            or os.getenv("GROQ_API_KEY", "")
            or getattr(settings, "API_KEY", "")
            or os.getenv("API_KEY", "")
        )
        self.model = (
            getattr(settings, "GROQ_GRADING_MODEL", "")
            or os.getenv("GROQ_GRADING_MODEL", "")
            or getattr(settings, "GROQ_ASSESSMENT_MODEL", "")
            or os.getenv("GROQ_ASSESSMENT_MODEL", "")
            or "openai/gpt-oss-120b"
        )
        self.max_completion_tokens = int(
            getattr(settings, "GROQ_GRADING_MAX_COMPLETION_TOKENS", 1600)
            or os.getenv("GROQ_GRADING_MAX_COMPLETION_TOKENS", "1600")
        )
        self.rate_limit_attempts = int(
            getattr(settings, "GROQ_RATE_LIMIT_RETRIES", 10)
            or os.getenv("GROQ_RATE_LIMIT_RETRIES", "10")
        )
        if not api_key:
            raise AnswerEvaluationError("GROQ_API_KEY is missing.")

        try:
            self.client = Groq(api_key=api_key, max_retries=0)
        except TypeError:  # older SDK compatibility
            self.client = Groq(api_key=api_key)

    def evaluate(
        self,
        *,
        question_payload,
        student_answer,
        target_skill_idea_codes=None,
        allowed_misconceptions=None,
    ):
        steps = self._normalize_steps(student_answer)
        if not steps:
            raise AnswerEvaluationError("At least one mathematical step is required.")

        allowed_misconceptions = [
            {
                "code": item.get("code", ""),
                "description": str(item.get("description", ""))[:500],
            }
            for item in (allowed_misconceptions or [])
            if isinstance(item, dict) and item.get("code")
        ][:10]
        target_codes = list(dict.fromkeys(target_skill_idea_codes or []))

        # Keep only grading evidence. Do not resend UI metadata/history to Groq.
        payload = {
            "question": {
                "statement_blocks": question_payload.get("statement_blocks", []),
                "answer_type": question_payload.get("answer_type", "multi_step"),
                "correct_answer_latex": question_payload.get("correct_answer_latex", ""),
                "reference_solution_steps": question_payload.get("solution_steps", []),
                "required_elements": (
                    question_payload.get("grading_rubric", {}).get("required_elements", [])
                ),
            },
            "student_steps": steps,
            "allowed_skill_idea_codes": target_codes,
            "allowed_misconceptions": allowed_misconceptions,
        }

        try:
            response = call_with_retries(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    temperature=0.05,
                    reasoning_effort="medium",
                    max_completion_tokens=self.max_completion_tokens,
                    response_format={
                        "type": "json_schema",
                        "json_schema": GRADING_JSON_SCHEMA,
                    },
                    messages=[
                        {"role": "system", "content": self._system_prompt()},
                        {
                            "role": "user",
                            "content": json.dumps(
                                payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    ],
                ),
                attempts=self.rate_limit_attempts,
                label="Groq answer grading",
            )
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise AnswerEvaluationError(
                    "خدمة التصحيح مشغولة مؤقتاً. أعد إرسال الحل بعد لحظات."
                ) from exc
            raise AnswerEvaluationError(
                "تعذر الاتصال بخدمة التصحيح مؤقتاً. لم تُسجل إجابتك كإجابة خاطئة."
            ) from exc

        content = response.choices[0].message.content
        if not content:
            raise AnswerEvaluationError("Groq returned an empty grading response.")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AnswerEvaluationError("تعذر قراءة نتيجة التصحيح. أعد إرسال الحل.") from exc

        score = max(0.0, min(float(result.get("score", 0.0)), 1.0))
        result["score"] = round(score, 4)

        # Never allow the model to invent taxonomy codes.
        allowed_target_codes = set(target_codes)
        result["mastered_skill_idea_codes"] = [
            code
            for code in result.get("mastered_skill_idea_codes", [])
            if code in allowed_target_codes
        ]
        result["weak_skill_idea_codes"] = [
            code
            for code in result.get("weak_skill_idea_codes", [])
            if code in allowed_target_codes
        ]

        allowed_error_codes = {item["code"] for item in allowed_misconceptions}
        result["detected_misconception_codes"] = [
            code
            for code in result.get("detected_misconception_codes", [])
            if code in allowed_error_codes
        ]

        is_correct = result.get("verdict") == "correct" and score >= 0.85

        # The server, not the LLM, owns mastery state.
        if allowed_target_codes:
            if is_correct:
                result["mastered_skill_idea_codes"] = sorted(allowed_target_codes)
                result["weak_skill_idea_codes"] = []
                result["should_retry"] = False
            else:
                result["mastered_skill_idea_codes"] = []
                result["weak_skill_idea_codes"] = sorted(allowed_target_codes)
                result["should_retry"] = True

        return {
            "is_correct": bool(is_correct),
            "score": score,
            "feedback": result,
            "detected_misconception_codes": result.get(
                "detected_misconception_codes", []
            ),
        }

    @staticmethod
    def _normalize_steps(student_answer):
        if isinstance(student_answer, dict):
            raw_steps = student_answer.get("steps", [])
        elif isinstance(student_answer, list):
            raw_steps = student_answer
        else:
            raw_steps = []

        output = []
        for index, step in enumerate(raw_steps, start=1):
            if isinstance(step, str):
                text = ""
                latex = step.strip()
            elif isinstance(step, dict):
                text = str(step.get("text") or step.get("explanation") or "").strip()
                latex = str(step.get("latex") or "").strip()
            else:
                text = ""
                latex = ""
            if text or latex:
                output.append({
                    "step_number": index,
                    "explanation": text[:1200],
                    "latex": latex[:2500],
                })
        return output[:30]

    @staticmethod
    def _system_prompt():
        return """
أنت أستاذ رياضيات للبكالوريا الجزائرية. صحح الحل خطوة بخطوة وبالمعنى الرياضي.
- اقبل أي طريقة مكافئة صحيحة ولا تعاقب اختلاف LaTeX.
- اذكر ما كان صحيحاً، وحدد أول خطأ وسببه وتصحيحه.
- افهم شرح التلميذ العربي مع كتابته الرياضية معاً؛ لا تعتمد على LaTeX وحده.
- أعط نقاطاً جزئية للتقدم الحقيقي.
- ميّز بين الخطأ الحسابي والخطأ المفاهيمي.
- next_hint عملي ومحدد.
- في teacher_message وwhat_was_correct وissue وwhy وnext_hint: اكتب العربية بشكل طبيعي، وأحط أي صيغة رياضية داخل $...$ حتى تعرضها الواجهة بشكل جميل، مثال: نحسب $u_{n+1}=2u_n+3$.
- correct_solution_steps تكون LaTeX فقط.
- score بين 0 و1، وcorrect فقط عند score>=0.85 مع اكتمال الفكرة المطلوبة.
- لا تخترع skill/misconception codes؛ استعمل المسموح فقط.
- لا تعتبر جواباً نهائياً بلا خطوات كافياً لسؤال multi_step.
""".strip()


DeterministicAnswerEvaluator = TeacherAnswerEvaluator
