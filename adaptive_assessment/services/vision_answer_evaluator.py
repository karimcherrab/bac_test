import base64
import json
import os
import logging
import re

from django.conf import settings

from adaptive_assessment.services.groq_resilience import call_with_retries, is_rate_limit_error

try:
    import groq
    Groq = groq.Groq
except ImportError:  # pragma: no cover
    groq = None
    Groq = None


logger = logging.getLogger(__name__)


class VisionAnswerEvaluationError(RuntimeError):
    def __init__(self, message, *, provider_detail="", provider_status=None):
        super().__init__(message)
        self.provider_detail = str(provider_detail or "")
        self.provider_status = provider_status


class VisionAnswerUnreadable(RuntimeError):
    def __init__(self, message, *, quality_notes=None):
        super().__init__(message)
        self.quality_notes = quality_notes or []


class VisionTeacherAnswerEvaluator:
    """Read handwritten solution images and return the same teacher feedback contract."""

    def __init__(self):
        if Groq is None:
            raise VisionAnswerEvaluationError("مكتبة Groq غير مثبتة على الخادم.")

        api_key = (
            getattr(settings, "GROQ_API_KEY", "")
            or os.getenv("GROQ_API_KEY", "")
            or getattr(settings, "API_KEY", "")
            or os.getenv("API_KEY", "")
        )
        if not api_key:
            raise VisionAnswerEvaluationError("مفتاح خدمة التصحيح غير مضبوط.")

        self.model = (
            getattr(settings, "GROQ_VISION_GRADING_MODEL", "")
            or os.getenv("GROQ_VISION_GRADING_MODEL", "")
            or "qwen/qwen3.6-27b"
        )
        self.max_completion_tokens = int(
            getattr(settings, "GROQ_VISION_MAX_COMPLETION_TOKENS", 2400)
            or os.getenv("GROQ_VISION_MAX_COMPLETION_TOKENS", "2400")
        )
        self.rate_limit_attempts = int(
            getattr(settings, "GROQ_RATE_LIMIT_RETRIES", 10)
            or os.getenv("GROQ_RATE_LIMIT_RETRIES", "10")
        )
        self.json_attempts = max(1, min(int(
            getattr(settings, "GROQ_VISION_JSON_RETRIES", 3)
            or os.getenv("GROQ_VISION_JSON_RETRIES", "3")
        ), 5))

        try:
            self.client = Groq(api_key=api_key, max_retries=0)
        except TypeError:  # pragma: no cover
            self.client = Groq(api_key=api_key)

    def evaluate(
        self,
        *,
        question_payload,
        prepared_images,
        target_skill_idea_codes=None,
        allowed_misconceptions=None,
    ):
        if not prepared_images:
            raise VisionAnswerEvaluationError("لم تصل أي صورة للحل.")

        target_codes = list(dict.fromkeys(target_skill_idea_codes or []))
        allowed_misconceptions = [
            {
                "code": item.get("code", ""),
                "description": str(item.get("description", ""))[:500],
            }
            for item in (allowed_misconceptions or [])
            if isinstance(item, dict) and item.get("code")
        ][:10]

        grading_context = {
            "question": {
                "statement_blocks": question_payload.get("statement_blocks", []),
                "answer_type": question_payload.get("answer_type", "multi_step"),
                "correct_answer_latex": question_payload.get("correct_answer_latex", ""),
                "reference_solution_steps": question_payload.get("solution_steps", []),
                "required_elements": question_payload.get("grading_rubric", {}).get(
                    "required_elements", []
                ),
            },
            "allowed_skill_idea_codes": target_codes,
            "allowed_misconceptions": allowed_misconceptions,
        }

        user_content = [
            {
                "type": "text",
                "text": (
                    "صحح حل التلميذ المكتوب في الصور المرفقة لهذا التمرين. "
                    "الصور مرتبة حسب الصفحات.\n"
                    + json.dumps(grading_context, ensure_ascii=False, separators=(",", ":"))
                ),
            }
        ]
        for item in prepared_images:
            encoded = base64.b64encode(item.content).decode("ascii")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{item.mime_type};base64,{encoded}",
                    },
                }
            )

        response = None
        last_json_error = None

        # JSON Object Mode is supported by the vision model, but it is not
        # strict constrained decoding. Groq can therefore reject an otherwise
        # correct visual analysis if the final JSON is cut off or malformed.
        # Retry ONLY that content-format failure; 429/5xx retries remain inside
        # call_with_retries and do not consume these JSON attempts.
        for json_attempt in range(1, self.json_attempts + 1):
            retry_note = ""
            if json_attempt > 1:
                retry_note = (
                    "\nمحاولة سابقة فشلت فقط لأن JSON لم يُغلق بشكل صحيح. "
                    "أعد التصحيح من البداية بإجابات أقصر جداً. لا تكتب شرحاً طويلاً، "
                    "ولا تترك أي قوس أو علامة اقتباس مفتوحة."
                )

            attempt_messages = [
                {
                    "role": "system",
                    "content": self._system_prompt() + retry_note,
                },
                {"role": "user", "content": user_content},
            ]

            try:
                response = call_with_retries(
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        temperature=0.0,
                        reasoning_effort="none",
                        max_completion_tokens=self.max_completion_tokens,
                        response_format={"type": "json_object"},
                        messages=attempt_messages,
                    ),
                    attempts=self.rate_limit_attempts,
                    label="Groq vision answer grading",
                )
                break

            except Exception as exc:
                if self._is_json_generation_failure(exc):
                    last_json_error = exc
                    logger.warning(
                        "Vision JSON generation failed; retrying content (%s/%s): %s",
                        json_attempt,
                        self.json_attempts,
                        str(exc)[:1200],
                    )
                    if json_attempt < self.json_attempts:
                        continue
                    raise VisionAnswerEvaluationError(
                        "تمت قراءة الحل، لكن تعذر تكوين نتيجة التصحيح بشكل منظم. أعد الإرسال مرة أخرى.",
                        provider_detail=str(exc)[:4000],
                        provider_status=400,
                    ) from exc

                # Keep the real provider error in server logs. Never expose
                # secrets/API keys in production.
                status_code = getattr(exc, "status_code", None)
                if status_code is None:
                    exc_response = getattr(exc, "response", None)
                    status_code = getattr(exc_response, "status_code", None)

                provider_detail = str(exc)[:4000]
                logger.exception(
                    "Vision grading failed (model=%s, status=%s): %s",
                    self.model,
                    status_code,
                    provider_detail,
                )

                if is_rate_limit_error(exc):
                    raise VisionAnswerEvaluationError(
                        "خدمة قراءة الصور مشغولة مؤقتًا بسبب كثرة الطلبات. أعد الإرسال بعد لحظات.",
                        provider_detail=provider_detail,
                        provider_status=status_code or 429,
                    ) from exc

                text = provider_detail.lower()
                if status_code in {401, 403} or any(
                    marker in text
                    for marker in (
                        "invalid api key",
                        "authentication",
                        "unauthorized",
                        "permission",
                        "not permitted",
                    )
                ):
                    raise VisionAnswerEvaluationError(
                        "خدمة قراءة الصور غير مفعلة لهذا الخادم. تحقق من مفتاح Groq وصلاحية النموذج البصري.",
                        provider_detail=provider_detail,
                        provider_status=status_code,
                    ) from exc

                if status_code == 413 or "too large" in text or "20mb" in text:
                    raise VisionAnswerEvaluationError(
                        "حجم صور الحل أكبر من الحد المسموح. التقط صورًا أوضح بحجم أصغر.",
                        provider_detail=provider_detail,
                        provider_status=status_code,
                    ) from exc

                if status_code == 400:
                    if "model" in text and any(
                        marker in text
                        for marker in ("does not exist", "not found", "decommission", "unsupported")
                    ):
                        message = "نموذج قراءة الصور غير متاح على حساب Groq الحالي. تحقق من GROQ_VISION_GRADING_MODEL."
                    elif "image" in text:
                        message = "رفضت خدمة القراءة إحدى الصور. أعد تصوير الحل بصيغة واضحة ثم حاول من جديد."
                    else:
                        message = "رفضت خدمة قراءة الصور الطلب. راجع سجل Django لمعرفة السبب التقني الدقيق."
                    raise VisionAnswerEvaluationError(
                        message,
                        provider_detail=provider_detail,
                        provider_status=status_code,
                    ) from exc

                raise VisionAnswerEvaluationError(
                    "تعذر الاتصال بخدمة قراءة الحل مؤقتًا. لم تُسجل المحاولة كإجابة خاطئة.",
                    provider_detail=provider_detail,
                    provider_status=status_code,
                ) from exc

        if response is None:
            detail = str(last_json_error or "")[:4000]
            raise VisionAnswerEvaluationError(
                "تعذر تكوين نتيجة التصحيح. أعد الإرسال مرة أخرى.",
                provider_detail=detail,
                provider_status=400 if last_json_error else None,
            )

        content = response.choices[0].message.content
        if not content:
            raise VisionAnswerEvaluationError("لم تصل نتيجة من خدمة قراءة الحل.")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise VisionAnswerEvaluationError("تعذر فهم نتيجة قراءة الصورة. أعد المحاولة.") from exc

        self._validate_shape(result)

        readability = str(result.get("solution_readability") or "").lower()
        if readability != "readable":
            notes = [str(x) for x in (result.get("image_quality_notes") or []) if str(x).strip()][:5]
            message = str(result.get("teacher_message") or "").strip()
            raise VisionAnswerUnreadable(
                message or "لم أستطع قراءة الحل بوضوح. أعد تصوير الورقة كاملة وبإضاءة أفضل.",
                quality_notes=notes,
            )

        score = max(0.0, min(float(result.get("score", 0.0)), 1.0))
        score = round(score, 4)
        result["score"] = score

        allowed_target_codes = set(target_codes)
        allowed_error_codes = {item["code"] for item in allowed_misconceptions}

        # Never let the vision model invent taxonomy codes.
        result["detected_misconception_codes"] = [
            code
            for code in result.get("detected_misconception_codes", [])
            if code in allowed_error_codes
        ]

        is_correct = result.get("verdict") == "correct" and score >= 0.85
        if allowed_target_codes:
            if is_correct:
                result["mastered_skill_idea_codes"] = sorted(allowed_target_codes)
                result["weak_skill_idea_codes"] = []
                result["should_retry"] = False
            else:
                result["mastered_skill_idea_codes"] = []
                result["weak_skill_idea_codes"] = sorted(allowed_target_codes)
                result["should_retry"] = True
        else:
            result["mastered_skill_idea_codes"] = []
            result["weak_skill_idea_codes"] = []

        # Keep useful visual metadata in feedback, without exposing chain-of-thought.
        result["solution_readability"] = "readable"
        result["image_quality_notes"] = [
            str(x) for x in (result.get("image_quality_notes") or []) if str(x).strip()
        ][:5]
        result["observed_solution_summary"] = str(
            result.get("observed_solution_summary") or ""
        )[:2500]

        return {
            "is_correct": bool(is_correct),
            "score": score,
            "feedback": result,
            "detected_misconception_codes": result.get(
                "detected_misconception_codes", []
            ),
        }

    @staticmethod
    def _is_json_generation_failure(exc):
        """Groq JSON-object failures are content retries, not service outages."""
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        text = str(exc).lower()
        return status == 400 and any(
            marker in text
            for marker in (
                "json_validate_failed",
                "failed to generate json",
                "failed_generation",
                "invalid json",
            )
        )

    @staticmethod
    def _validate_shape(result):
        if not isinstance(result, dict):
            raise VisionAnswerEvaluationError("نتيجة قراءة الصورة غير صالحة.")

        verdict = result.get("verdict")
        if verdict not in {"correct", "partially_correct", "incorrect"}:
            raise VisionAnswerEvaluationError("تعذر تحديد نتيجة الحل المصوّر.")

        readability = str(result.get("solution_readability") or "").lower()
        if readability not in {"readable", "needs_retake"}:
            raise VisionAnswerEvaluationError("تعذر تحديد وضوح صورة الحل.")

        for key in (
            "teacher_message",
            "next_hint",
            "what_was_correct",
            "errors",
            "correct_solution_steps",
            "detected_misconception_codes",
            "image_quality_notes",
            "observed_solution_summary",
        ):
            if key not in result:
                raise VisionAnswerEvaluationError("نتيجة قراءة الصورة ناقصة. أعد المحاولة.")

        try:
            float(result.get("score", 0.0))
        except (TypeError, ValueError) as exc:
            raise VisionAnswerEvaluationError("درجة التصحيح غير صالحة.") from exc

        if not isinstance(result.get("errors"), list):
            raise VisionAnswerEvaluationError("تفاصيل أخطاء الحل غير صالحة.")
        if not isinstance(result.get("what_was_correct"), list):
            raise VisionAnswerEvaluationError("تفاصيل الجزء الصحيح غير صالحة.")

        cleaned_errors = []
        for index, item in enumerate(result.get("errors") or [], start=1):
            if not isinstance(item, dict):
                continue
            cleaned_errors.append(
                {
                    "step_number": max(1, int(item.get("step_number") or index)),
                    "issue": str(item.get("issue") or "")[:1200],
                    "why": str(item.get("why") or "")[:1800],
                    "corrected_latex": str(item.get("corrected_latex") or "")[:2500],
                }
            )
        result["errors"] = cleaned_errors
        result["what_was_correct"] = [str(x)[:1500] for x in result.get("what_was_correct") or []][:12]
        result["correct_solution_steps"] = [
            str(x)[:2500] for x in result.get("correct_solution_steps") or []
        ][:30]

    @staticmethod
    def _system_prompt():
        return r"""
أنت أستاذ رياضيات للبكالوريا الجزائرية، وتصحح ورقة حل مصوّرة كما يفعل أستاذ حقيقي.

المهمة:
1) افحص أولاً هل كل صفحات الحل مقروءة وكاملة. إذا كانت الكتابة شديدة الغموض، الورقة مقطوعة، أو لا يمكن الوثوق بقراءة الحل، أرجع solution_readability = "needs_retake". لا تخمّن ولا تعاقب التلميذ.
2) إذا كانت الصور مقروءة، اقرأ تسلسل الحل من الصفحة الأولى إلى الأخيرة، وافهم الرموز الرياضية والخط العربي قدر الإمكان.
3) قارن منطق الحل بالسؤال والحل المرجعي، لا بالشكل النصي. اقبل أي طريقة رياضية مكافئة صحيحة.
4) اذكر ما كان صحيحاً وحدد أول خطأ حقيقي وسببه وكيف يصحح. أعط نقاطاً جزئية للتقدم الحقيقي.
5) لا تعتبر اختلاف شكل الخط أو الرموز أو الترتيب البسيط خطأ إذا كان المعنى الرياضي صحيحاً.
6) لا تخترع خطوة لا تراها في الصورة. إذا رمز واحد فقط غير واضح لكن بقية السياق يحسمه بأمان يمكنك فهمه؛ إذا كان الغموض يغير صحة الحل فاطلب إعادة التصوير.
7) لا تذكر أي معلومات شخصية تراها في الورقة ولا تستخرج أسماء أو بيانات خارج الحل الرياضي.
8) في teacher_message و what_was_correct و errors يمكنك وضع الصيغ الرياضية القصيرة داخل $...$. اجعل next_hint جملة عربية قصيرة جداً بلا LaTeX لتقليل أخطاء JSON. correct_solution_steps تكون LaTeX فقط.
9) score عدد بين 0 و1. verdict = correct فقط إذا كانت الفكرة المطلوبة متقنة والحل يستحق 0.85 على الأقل.
10) استعمل فقط misconception codes المسموح بها ولا تخترع أكواداً.
11) اختصر جداً: teacher_message بحد أقصى 3 جمل، what_was_correct بحد أقصى 4 عناصر، errors بحد أقصى 4 عناصر، image_quality_notes بحد أقصى 3 عناصر، correct_solution_steps بحد أقصى 8 خطوات.
12) JSON صالح إلزامياً: أغلق كل علامات الاقتباس والأقواس. لا تضف فاصلة بعد آخر عنصر. لا تكتب أي شيء قبل JSON أو بعده.

أرجع JSON فقط بهذا الشكل، مع جميع المفاتيح دائماً:
{
  "solution_readability": "readable" أو "needs_retake",
  "image_quality_notes": ["..."],
  "observed_solution_summary": "وصف مختصر لما قرأته من الحل، بلا كشف بيانات شخصية",
  "verdict": "correct" أو "partially_correct" أو "incorrect",
  "score": 0.0,
  "teacher_message": "...",
  "what_was_correct": ["..."],
  "errors": [
    {"step_number": 1, "issue": "...", "why": "...", "corrected_latex": "..."}
  ],
  "next_hint": "...",
  "correct_solution_steps": ["..."],
  "mastered_skill_idea_codes": [],
  "weak_skill_idea_codes": [],
  "detected_misconception_codes": [],
  "should_retry": true
}
""".strip()
