import json
import os

from django.conf import settings
from adaptive_assessment.schemas import QUESTION_JSON_SCHEMA
from adaptive_assessment.services.groq_resilience import call_with_retries, is_rate_limit_error

try:
    import groq
    Groq = groq.Groq
    BadRequestError = getattr(groq, "BadRequestError", ())
except ImportError:  # pragma: no cover
    groq = None
    Groq = None
    BadRequestError = ()


class GroqConfigurationError(RuntimeError):
    pass


class GroqQuestionGenerationError(RuntimeError):
    pass


class GroqQuestionGenerator:
    """Generate one validated exercise for one deterministic lesson/BAC target."""

    GENERATION_ATTEMPTS = 3

    def __init__(self):
        if Groq is None:
            raise GroqConfigurationError("Install the Groq SDK: pip install -U groq")

        api_key = (
            getattr(settings, "GROQ_API_KEY", "")
            or os.getenv("GROQ_API_KEY", "")
            or getattr(settings, "API_KEY", "")
            or os.getenv("API_KEY", "")
        )
        self.model = (
            getattr(settings, "GROQ_ASSESSMENT_MODEL", "")
            or os.getenv("GROQ_ASSESSMENT_MODEL", "")
            or os.getenv("GROQ_EXERCISE_MODEL", "")
            or "openai/gpt-oss-120b"
        )
        self.max_completion_tokens = int(
            getattr(settings, "GROQ_QUESTION_MAX_COMPLETION_TOKENS", 2200)
            or os.getenv("GROQ_QUESTION_MAX_COMPLETION_TOKENS", "2200")
        )
        self.rate_limit_attempts = int(
            getattr(settings, "GROQ_RATE_LIMIT_RETRIES", 10)
            or os.getenv("GROQ_RATE_LIMIT_RETRIES", "10")
        )
        if not api_key:
            raise GroqConfigurationError("GROQ_API_KEY is missing.")

        try:
            self.client = Groq(api_key=api_key, max_retries=0)
        except TypeError:  # older SDK compatibility
            self.client = Groq(api_key=api_key)

    def _request(self, prompt):
        return call_with_retries(
            lambda: self.client.chat.completions.create(
                model=self.model,
                temperature=0.05,
                reasoning_effort="medium",
                max_completion_tokens=self.max_completion_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": QUESTION_JSON_SCHEMA,
                },
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
            ),
            attempts=self.rate_limit_attempts,
            label="Groq question generation",
        )

    def generate(self, *, slot, source_context, retry_feedback=None):
        if slot.get("source_type") not in {"skill", "bac"}:
            raise GroqQuestionGenerationError("Unsupported assessment source type.")

        expected_policy = {
            "skill": "single_axis_lesson_idea",
            "bac": "single_documented_bac_idea",
        }[slot["source_type"]]
        if source_context.get("policy") != expected_policy:
            raise GroqQuestionGenerationError("Source context policy mismatch.")

        prompt = self._build_prompt(slot, source_context, retry_feedback)
        last_error = None

        for attempt in range(1, self.GENERATION_ATTEMPTS + 1):
            try:
                response = self._request(prompt)
                content = response.choices[0].message.content
                if not content:
                    raise GroqQuestionGenerationError("Groq returned an empty response.")
                payload = json.loads(content)

                # Taxonomy is server-owned; the model may not invent/change these fields.
                payload["source_type"] = slot["source_type"]
                payload["skill_code"] = slot.get("skill_code", "")
                payload["bac_idea_code"] = slot.get("bac_idea_code", "")
                payload["variant_code"] = slot.get("variant_code", "")
                payload["difficulty"] = int(slot.get("difficulty", 1))
                payload["target_skill_idea_codes"] = list(
                    slot.get("target_skill_idea_codes") or []
                )
                payload["requires_external_data"] = False
                payload["ambiguous"] = False
                return payload

            except Exception as exc:
                last_error = exc
                if BadRequestError and isinstance(exc, BadRequestError):
                    text = str(exc).lower()
                    recoverable = any(
                        marker in text
                        for marker in (
                            "json_validate_failed",
                            "failed to generate json",
                            "failed_generation",
                            "invalid json",
                        )
                    )
                    if not recoverable:
                        raise GroqQuestionGenerationError(str(exc)) from exc
                elif not isinstance(exc, (json.JSONDecodeError, GroqQuestionGenerationError)):
                    if is_rate_limit_error(exc):
                        raise GroqQuestionGenerationError(
                            "خدمة إنشاء الأسئلة مشغولة مؤقتاً. أعد المحاولة بعد لحظات."
                        ) from exc
                    raise GroqQuestionGenerationError(
                        "تعذر إنشاء السؤال مؤقتاً بسبب اتصال خدمة الذكاء الاصطناعي."
                    ) from exc

                if attempt >= self.GENERATION_ATTEMPTS:
                    break

                prompt = self._build_prompt(
                    slot,
                    source_context,
                    {
                        "type": "generation_or_json_failure",
                        "instruction": "Regenerate from scratch with exact JSON and a simpler visual spec.",
                    },
                )

        raise GroqQuestionGenerationError(
            f"Could not generate a valid question after {self.GENERATION_ATTEMPTS} content attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _system_prompt():
        return r"""
أنت أستاذ رياضيات متخصص في البكالوريا الجزائرية ومصمم تمارين تعليمية دقيقة.
أنشئ سؤالاً واحداً فقط يقيس الفكرة التي حددها الخادم، ولا تضف فكرة أخرى.

إذا كان source_type=skill: اختبر lesson_idea وحدها بتمرين مباشر.
إذا كان source_type=bac: التزم bac_idea والـvariant إن وجد، واستلهم نمط البكالوريا دون نسخ سؤال تاريخي حرفياً.

قواعد المحتوى:
- statement_blocks: text للعربية فقط وmath لـLaTeX فقط. لا تخلط LaTeX داخل text.
- لا تستعمل \( أو \) داخل math block ولا تستعمل \u.
- solution_steps: LaTeX رياضي نظيف فقط، خطوة منطقية واحدة في كل عنصر، بلا جمل عربية داخل الصيغة.
- teacher_hint إذا احتوى رياضيات ضع الصيغة بين $...$.
- grading_rubric.max_score=1.0.
- السؤال self-contained وبالصعوبة المطلوبة.
- لا تخترع أكواداً أو سنوات أو حقائق خارج السياق.

قواعد الرسومات التعليمية (visuals):
- إذا كان التمرين أو الحل لا يحتاج رسماً أرجع visuals=[]. لا تضف رسماً للزينة.
- إذا كان فهم نص السؤال يحتاج منحنى/جدول تغيرات/جدول إشارة/شكل هندسي/مخطط، يجب إضافته placement="question".
- إذا كان الرسم مطلوباً فقط لشرح الحل، استعمل placement="solution" و after_step يحدد بعد أي خطوة يظهر؛ after_step=0 يعني قبل خطوات الحل.
- kind=function_graph: أعط x_min,x_max,y_min,y_max الصحيحة، وأرسل series كنقاط عددية مرتبة حسب x. استعمل عادة 16..36 نقطة لكل منحنى، وزد النقاط قرب الانعطافات أو المقاربات. لا تصل نقطتين عبر انقطاع؛ افصل الجزأين في series مختلفتين.
- kind=variation_table أو sign_table: استعمل columns وrows. عدد cells في كل row يساوي عدد columns. يمكن استعمال LaTeX قصير داخل الخلايا بين $...$.
- kind=data_table: نفس columns/rows لجدول معطيات عادي.
- kind=geometry أو diagram: استعمل commands فقط، بإحداثيات من 0 إلى 100 داخل viewBox منطقي.
  الصيغ المسموحة للـcommands فقط:
  line x1 y1 x2 y2 [label]
  arrow x1 y1 x2 y2 [label]
  point x y [label]
  circle cx cy r [label]
  rect x y width height [label]
  polyline x1,y1 x2,y2 ...
  polygon x1,y1 x2,y2 ...
  text x y النص
- لا ترسل SVG أو HTML أو JavaScript ولا روابط أو صور خارجية.
- العناوين caption/title بالعربية، قصيرة وواضحة.
- لكل visual املأ جميع الحقول الموجودة في schema؛ استعمل [] أو "" أو 0 للحقول غير المستعملة.
- الرسم جزء من صحة التمرين: يجب أن يطابق نص السؤال والحل تماماً.
""".strip()

    @staticmethod
    def _build_prompt(slot, source_context, retry_feedback=None):
        data = {
            "task": "generate_one_axis_mastery_question_with_optional_visuals",
            "target": {
                "source_type": slot.get("source_type"),
                "difficulty": int(slot.get("difficulty", 1)),
                "skill_idea_code": slot.get("skill_idea_code", ""),
                "bac_idea_code": slot.get("bac_idea_code", ""),
                "variant_code": slot.get("variant_code", ""),
            },
            "context": source_context,
            "visual_policy": {
                "render_engine": "safe_react_svg_and_tables",
                "draw_only_when_pedagogically_needed": True,
                "supports": [
                    "function_graph",
                    "variation_table",
                    "sign_table",
                    "geometry",
                    "diagram",
                    "data_table",
                ],
            },
        }
        if retry_feedback:
            instruction = (
                str(retry_feedback.get("instruction") or "")
                if isinstance(retry_feedback, dict)
                else ""
            )
            if instruction == "same_target_new_exercise_after_incorrect_answer":
                data["retry"] = (
                    "The student did not master this target. Generate a NEW and DIFFERENT exercise "
                    "for the exact same target and difficulty. Change numbers/context and regenerate any visual."
                )
            elif instruction == "next_target":
                data["retry"] = "Generate the exercise for this new target only."
            else:
                data["retry"] = (
                    "Previous output was invalid; regenerate exact JSON for the same target. "
                    "Keep visual data compact and mathematically consistent."
                )
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
