# tutor/services/llm/groq_answer_service.py

import json
import os

from django.conf import settings
from groq import Groq


class GroqAnswerService:

    MODEL = "openai/gpt-oss-120b"

    def __init__(self):
        api_key = (
                os.getenv("GROQ_API_KEY")
                or os.getenv("API_KEY")
        )
        if not api_key:
            raise RuntimeError(
                    "GROQ_API_KEY غير موجود."
                )


        self.client = Groq(
            api_key=api_key
        )

    def generate(
        self,
        *,
        question: str,
        context: str = "",
        history: list[dict] | None = None,
        mode: str = "rag",
    ) -> dict:

        history = history or []

        use_rag = (
            mode == "rag"
            and bool(context.strip())
        )

        if use_rag:
            knowledge_rule = """
اعتمد أساسًا على المحتوى التعليمي المسترجع من المنصة.
يمكنك إعادة صياغته وشرحه بشكل أوضح.

لا تضف معلومات تناقض المحتوى المسترجع.

إذا احتاج الشرح تعريفًا بسيطًا أو رابطًا منطقيًا عامًا
يمكنك استعمال معرفتك التعليمية العامة بشرط ألا تغيّر
المعلومة الموجودة في المصدر.
""".strip()

        else:
            knowledge_rule = """
لم يتم العثور على محتوى تعليمي مناسب في قاعدة بيانات المنصة.

في هذه الحالة:
- أجب باستعمال معرفتك العامة مباشرة.
- لا تقل للتلميذ إن المحتوى غير موجود.
- لا تقل "لا أستطيع الإجابة" لمجرد عدم وجود RAG.
- اشرح كأستاذ بكالوريا جزائري بطريقة بسيطة.
""".strip()

        system_prompt = f"""
أنت مساعد تعليمي ذكي موجه لتلاميذ البكالوريا الجزائرية.

{knowledge_rule}

قواعد الإجابة:

1. أجب باللغة العربية الواضحة والبسيطة.

2. عندما توجد صيغة رياضية أو فيزيائية:
   أرجعها في block من النوع "math"
   باستعمال LaTeX فقط.

مثال:
f'(x)=2x+3

يجب أن تصبح:
"latex": "f'(x)=2x+3"

3. إذا كان الحل يحتاج مراحل:
   استعمل block من النوع "steps".

4. إذا كان هناك شرح عادي:
   استعمل block من النوع "text".

5. إذا احتاج الشرح رسمًا بيانيًا مفيدًا:
   أرجع graph.
   لا تنشئ graph إذا لم يكن مفيدًا.

6. graph يجب أن يحتوي نقاطًا رقمية فقط يمكن رسمها في React.

7. لا تضع Markdown code fences.

8. لا تكتب JSON داخل نص.

9. لا تذكر RAG أو SOURCE أو database للتلميذ.

10. إذا كان السؤال بسيطًا، اجعل الجواب قصيرًا.

11. إذا كان السؤال تمرينًا، اجعل الحل متدرجًا وواضحًا.

يجب أن ترجع JSON صحيحًا فقط بهذا الشكل:

{{
  "mode": "{mode}",
  "title": "",
  "intro": "",
  "blocks": [
    {{
      "type": "text",
      "content": ""
    }},
    {{
      "type": "math",
      "latex": ""
    }},
    {{
      "type": "steps",
      "items": []
    }}
  ],
  "graph": null,
  "summary": ""
}}

بالنسبة إلى graph يمكن أن يكون:

{{
  "type": "cartesian",
  "x_label": "x",
  "y_label": "f(x)",
  "series": [
    {{
      "label": "f(x)",
      "points": [
        {{
          "x": 0,
          "y": 0
        }}
      ]
    }}
  ]
}}

احذف أي block غير مطلوب.
""".strip()

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        for message in history[-8:]:
            role = message.get("role")
            content = message.get("content")

            if (
                role in {"user", "assistant"}
                and content
            ):
                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        user_parts = [
            f"سؤال التلميذ:\n{question}"
        ]

        if use_rag:
            user_parts.append(
                "المحتوى التعليمي المسترجع:\n"
                + context
            )

        user_prompt = "\n\n".join(
            user_parts
        )

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        response = (
            self.client
            .chat
            .completions
            .create(
                model=self.MODEL,
                messages=messages,
                temperature=0.2,

                response_format={
                    "type": "json_object",
                },
            )
        )

        raw_content = (
            response
            .choices[0]
            .message
            .content
            or "{}"
        )

        try:
            result = json.loads(
                raw_content
            )

        except json.JSONDecodeError:
            return {
                "mode": mode,
                "title": "",
                "intro": raw_content.strip(),
                "blocks": [],
                "graph": None,
                "summary": "",
            }

        return self._normalize(
            result=result,
            mode=mode,
        )

    def _normalize(
        self,
        *,
        result: dict,
        mode: str,
    ) -> dict:

        if not isinstance(
            result,
            dict,
        ):
            result = {}

        blocks = result.get(
            "blocks",
            [],
        )

        if not isinstance(
            blocks,
            list,
        ):
            blocks = []

        graph = result.get(
            "graph"
        )

        if not isinstance(
            graph,
            dict,
        ):
            graph = None

        return {
            "mode": mode,

            "title": str(
                result.get(
                    "title",
                    "",
                )
                or ""
            ).strip(),

            "intro": str(
                result.get(
                    "intro",
                    "",
                )
                or ""
            ).strip(),

            "blocks": blocks,

            "graph": graph,

            "summary": str(
                result.get(
                    "summary",
                    "",
                )
                or ""
            ).strip(),
        }