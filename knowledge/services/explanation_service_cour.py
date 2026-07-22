# knowledge/services/explanation_service_cour.py

import json
import re
from typing import Any

from course.models import Axis
from knowledge.retrieval.answer_generator import AnswerGenerator
from knowledge.retrieval.context_builder import BuiltContext


class ExplainCourService:
    """
    خدمة توليد شرح مبسط وتفاعلي لدرس رياضيات.

    النتيجة تكون JSON منظّمًا لعرضه في واجهة React على شكل Cards.
    """

    MAX_LESSON_CONTENT_LENGTH = 14_000

    def __init__(self):
        self.generator = AnswerGenerator()

    def clean_model_response(self, text: str) -> str:
        """
        تنظيف إجابة النموذج قبل محاولة تحويلها إلى JSON.
        """
        if not text:
            return ""

        text = text.strip()

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

    def extract_json(self, text: str) -> dict:
        """
        استخراج JSON من إجابة النموذج، حتى إذا أضاف نصًا قبله أو بعده.
        """
        cleaned_text = self.clean_model_response(text)

        if not cleaned_text:
            return {
                "title": "شرح الدرس",
                "lesson_goal": "",
                "learning_path": [],
            }

        try:
            parsed = json.loads(cleaned_text)

            if isinstance(parsed, dict):
                return parsed

        except (json.JSONDecodeError, TypeError):
            pass

        start_index = cleaned_text.find("{")
        end_index = cleaned_text.rfind("}")

        if start_index != -1 and end_index != -1:
            possible_json = cleaned_text[start_index:end_index + 1]

            try:
                parsed = json.loads(possible_json)

                if isinstance(parsed, dict):
                    return parsed

            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "title": "شرح الدرس",
            "lesson_goal": "",
            "learning_path": [],
            "raw_answer": cleaned_text,
        }

    def normalize_text(self, value: Any, default: str = "") -> str:
        """
        ضمان أن القيمة نص وليست None أو نوعًا غير متوقع.
        """
        if value is None:
            return default

        if isinstance(value, str):
            return value.strip()

        return str(value).strip()

    def normalize_answer(self, answer: Any) -> dict:
        """
        ضمان وجود الحقول الأساسية بالتنسيق الصحيح.
        """
        if not isinstance(answer, dict):
            return {
                "title": "شرح الدرس",
                "lesson_goal": "",
                "learning_path": [],
                "raw_answer": str(answer),
            }

        normalized = {
            "title": self.normalize_text(
                answer.get("title"),
                "شرح الدرس",
            ),
            "lesson_goal": self.normalize_text(
                answer.get("lesson_goal"),
            ),
            "estimated_duration": self.normalize_text(
                answer.get("estimated_duration"),
                "15 دقيقة",
            ),
            "learning_path": answer.get("learning_path", []),
        }

        if not isinstance(normalized["learning_path"], list):
            normalized["learning_path"] = []

        normalized_steps = []

        for step in normalized["learning_path"]:
            if isinstance(step, dict):
                normalized_steps.append(step)

        normalized["learning_path"] = normalized_steps

        if "raw_answer" in answer:
            normalized["raw_answer"] = self.normalize_text(
                answer.get("raw_answer")
            )

        return normalized

    def limit_lesson_content(self, content: str) -> str:
        """
        تقليل حجم محتوى الدرس لتجنب تجاوز حد Tokens.
        """
        content = self.normalize_text(content)

        if len(content) <= self.MAX_LESSON_CONTENT_LENGTH:
            return content

        return (
            content[:self.MAX_LESSON_CONTENT_LENGTH]
            + "\n\n[تم اختصار الجزء المتبقي بسبب طول محتوى الدرس.]"
        )

    def build_prompt(
        self,
        axis_title: str,
        lesson_title: str,
        lesson_content: str,
    ) -> str:
        """
        بناء Prompt مخصص لشرح درس رياضيات بطريقة تدريجية.
        """
        return f"""
أنت أستاذ رياضيات جزائري خبير في تدريس تلاميذ السنة الثالثة ثانوي
والتحضير لشهادة البكالوريا.

مهمتك ليست تلخيص الدرس فقط، بل جعل التلميذ يفهم الفكرة تدريجيًا
كما لو أنك تشرح له داخل القسم.

بيانات الدرس:

عنوان المحور:
{axis_title}

عنوان الدرس:
{lesson_title}

محتوى الدرس المعتمد:
{lesson_content}

تعليمات الإخراج المهمة جدًا:

1. أجب بكائن JSON صحيح فقط.
2. لا تستعمل Markdown.
3. لا تكتب ```json أو ```.
4. لا تضف أي كلام قبل JSON أو بعده.
5. استعمل علامات الاقتباس المزدوجة في JSON.
6. لا تضع فاصلة بعد آخر عنصر.
7. لا تترك أي حقل فارغًا إذا كان محتوى الدرس يسمح بملئه.
8. لا تخترع قوانين أو معلومات غير موجودة في الدرس.
9. اجعل جميع الجمل قصيرة وواضحة.
10. لا تكتب مقالات أو فقرات طويلة.

قواعد LaTeX:

- اكتب الصيغ الرياضية القصيرة داخل:
  \\( ... \\)

- مثال صحيح:
  \\(u_{{n+1}}=2u_n+1\\)

- مثال صحيح:
  \\(u_n=u_0+n r\\)

- لا تستعمل:
  \\[ ... \\]

- لا تستعمل:
  $$ ... $$

- لا تستعمل أوامر تكبير الخط مثل:
  \\displaystyle
  \\Large
  \\Huge

- لا تضع جملة عربية كاملة داخل LaTeX.
- اجعل الصيغة منفصلة عن الكلمات العربية قدر الإمكان.
- لا تكتب أكثر من صيغة رياضية واحدة طويلة في الجملة نفسها.
- لا تكرر القانون نفسه عدة مرات.
- يجب الهروب من الشرطة المائلة داخل JSON.
  مثال:
  "\\\\frac{{1}}{{2}}"

طريقة الشرح:

- لا تبدأ بالتعريف الرسمي.
- ابدأ بمثال عددي بسيط أو موقف يستطيع التلميذ تخيله.
- اجعل التلميذ يلاحظ قبل إعطائه القاعدة.
- انتقل وفق الترتيب:
  نلاحظ ← نفكر ← نحسب ← نستنتج.
- بعد كل فكرة مهمة، اطرح سؤالًا صغيرًا للتأكد من الفهم.
- لا تجعل السؤال صعبًا قبل شرح الفكرة.
- استعمل لغة عربية سهلة ومباشرة.
- اشرح سبب كل عملية حسابية.
- لا تقل فقط "نطبق القانون"، بل وضح لماذا نستعمله.
- عند وجود رمز جديد، اشرح معناه.
- عند وجود برهان، قسمه إلى خطوات قصيرة.
- اجعل المثال التطبيقي مختلفًا قليلًا عن مثال البداية.
- تجنب التكرار والحشو.
- كل Card يجب أن يحتوي فكرة واحدة رئيسية فقط.
- اجعل الشرح مناسبًا لتلميذ مستواه متوسط.
- يجب ألا يتجاوز الشرح عادة 9 مراحل.
- مدة الدرس المقترحة بين 10 و20 دقيقة.

الشكل المطلوب:

{{
  "title": "عنوان واضح وقصير للدرس",
  "lesson_goal": "جملة قصيرة توضح ماذا سيفهم التلميذ",
  "estimated_duration": "15 دقيقة",
  "learning_path": [
    {{
      "id": "step_1",
      "type": "hook",
      "title": "لنبدأ بفكرة بسيطة",
      "content": "موقف بسيط أو مثال عددي قصير مرتبط مباشرة بالدرس.",
      "teacher_message": "جملة قصيرة تجعل التلميذ يفكر.",
      "action": "فكر في الإجابة قبل متابعة الشرح."
    }},
    {{
      "id": "step_2",
      "type": "warm_up_question",
      "title": "ماذا تلاحظ؟",
      "question": "سؤال سهل مبني على مثال البداية.",
      "expected_answer": "إجابة قصيرة وواضحة.",
      "teacher_feedback": "تعليق يشجع التلميذ ويصحح الفكرة.",
      "hint": "تلميح قصير دون إعطاء الجواب مباشرة."
    }},
    {{
      "id": "step_3",
      "type": "guided_explanation",
      "title": "نبني الفكرة خطوة بخطوة",
      "content": "شرح قصير يبدأ بالملاحظة ثم الحساب ثم الاستنتاج.",
      "key_idea": "أهم فكرة يجب أن يتذكرها التلميذ.",
      "checkpoint_question": "سؤال قصير جدًا للتأكد من الفهم.",
      "checkpoint_answer": "الجواب المنتظر.",
      "teacher_feedback": "توضيح بسيط للجواب."
    }},
    {{
      "id": "step_4",
      "type": "formal_definition",
      "title": "القاعدة الرياضية",
      "before_definition": "جملة تربط ما اكتشفه التلميذ بالتعريف.",
      "definition": "التعريف أو القانون بصيغة رياضية دقيقة ومختصرة.",
      "symbols": [
        {{
          "symbol": "رمز رياضي",
          "meaning": "معناه بكلمات بسيطة"
        }}
      ],
      "simple_meaning": "شرح القاعدة بلغة سهلة.",
      "memory_tip": "طريقة قصيرة تساعد على تذكرها."
    }},
    {{
      "id": "step_5",
      "type": "method",
      "title": "كيف أستعمل هذه الفكرة؟",
      "method_goal": "متى نستعمل هذه الطريقة؟",
      "steps": [
        {{
          "step_number": 1,
          "instruction": "تعليمة قصيرة.",
          "why": "سبب القيام بهذه الخطوة.",
          "calculation_template": "صيغة قصيرة إن وجدت.",
          "student_task": "ما الذي يجب على التلميذ فعله؟",
          "hint": "تلميح قصير."
        }}
      ],
      "conclusion_template": "صيغة قصيرة للاستنتاج النهائي."
    }},
    {{
      "id": "step_6",
      "type": "worked_example",
      "title": "مثال تطبيقي",
      "example_statement": "مثال قصير وواضح.",
      "given_data": [
        "المعطى الأول",
        "المعطى الثاني"
      ],
      "question": "المطلوب في المثال.",
      "steps": [
        {{
          "step_number": 1,
          "title": "عنوان قصير للخطوة.",
          "teacher_explanation": "لماذا نقوم بهذه الخطوة؟",
          "calculation": "حساب LaTeX قصير.",
          "result": "النتيجة المباشرة.",
          "next_question": "سؤال صغير يقود للخطوة التالية."
        }}
      ],
      "final_conclusion": "استنتاج المثال بجملة قصيرة."
    }},
    {{
      "id": "step_7",
      "type": "common_mistakes",
      "title": "انتبه إلى هذه الأخطاء",
      "mistakes": [
        {{
          "wrong_idea": "خطأ شائع عند التلميذ.",
          "why_wrong": "لماذا هو خطأ؟",
          "correction": "التصحيح الصحيح.",
          "teacher_tip": "نصيحة عملية لتجنب الخطأ."
        }}
      ]
    }},
    {{
      "id": "step_8",
      "type": "mini_quiz",
      "title": "تأكد من فهمك",
      "questions": [
        {{
          "question": "سؤال قصير مرتبط مباشرة بالدرس.",
          "choices": [
            "الاختيار الأول",
            "الاختيار الثاني",
            "الاختيار الثالث"
          ],
          "correct_answer": "نص الاختيار الصحيح نفسه.",
          "hint": "تلميح صغير.",
          "explanation": "سبب صحة الإجابة في جملة أو جملتين."
        }}
      ]
    }},
    {{
      "id": "step_9",
      "type": "visual_summary",
      "title": "الخلاصة التي تحفظها",
      "items": [
        "فكرة أساسية قصيرة.",
        "قانون أو طريقة قصيرة.",
        "تنبيه مهم."
      ],
      "method_template": [
        "أحدد المعطيات.",
        "أختار القانون المناسب.",
        "أحسب ثم أستنتج."
      ],
      "final_sentence": "جملة تشجيعية قصيرة."
    }}
  ]
}}

شروط إضافية:

- أنشئ فقط المراحل المناسبة فعلًا لمحتوى هذا الدرس.
- يمكن حذف مرحلة البرهان إذا لم يحتج الدرس إلى برهان.
- يمكن تغيير عنوان كل مرحلة ليتناسب مع محتوى الدرس.
- ضع من سؤال واحد إلى سؤالين فقط في mini_quiz.
- ضع من خطأ واحد إلى ثلاثة أخطاء فقط.
- ضع من خطوتين إلى أربع خطوات فقط في المثال.
- اجعل content وteacher_explanation أقل من 350 حرفًا غالبًا.
- اجعل lesson_goal أقل من 180 حرفًا.
- لا تكرر محتوى التعريف داخل الخلاصة حرفيًا.
- لا تستعمل كلمات معقدة دون شرحها.
"""

    def generate(self, axis_id: str):
        """
        توليد شرح الدرس انطلاقًا من معرف KnowledgeItem.
        """
        try:
            cour = (
                Axis.objects
                .get(
                    id=axis_id
                )
            )

        except Axis.DoesNotExist:
            return None

        lesson_title = self.normalize_text(
            cour.title,
            "درس رياضيات",
        )

        lesson_content = self.limit_lesson_content(
            cour.content
        )

        axis_title = ""

        if cour.axis:
            axis_title = self.normalize_text(
                cour.axis.title
            )

        prompt = self.build_prompt(
            axis_title=axis_title,
            lesson_title=lesson_title,
            lesson_content=lesson_content,
        )

        context = BuiltContext(
            question=(
                f"اشرح درس {lesson_title} "
                "بطريقة مبسطة وتفاعلية لتلميذ بكالوريا."
            ),
            intent="explain_course",
            context_text=prompt,
            items=[cour],
        )

        generated = self.generator.generate(context)

        answer = self.extract_json(
            generated.answer
        )

        answer = self.normalize_answer(answer)

        return {
            "mode": "cour_explication",
            "axis_id": str(cour.id),
            "axis_tag": (
                cour.axis.tag
                if cour.axis and hasattr(cour.axis, "tag")
                else ""
            ),
            "axis_title": axis_title,
            "lesson_title": lesson_title,
            "model": generated.model,
            "answer": answer,
        }