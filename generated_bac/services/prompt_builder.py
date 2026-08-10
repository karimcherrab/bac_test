from __future__ import annotations

import json
from typing import Any


class BacPromptBuilder:
    VISUAL_RULES = r"""
قواعد الرسومات (visuals):
- أضف الرسم عندما يكون مطلوبًا في السؤال أو ضروريًا لفهم الحل.
- إذا كان نص السؤال يحتوي أفعالًا مثل: ارسم، مثّل، خطّط، أنشئ الشكل، وضّح الدارة، حدّد موضع جهاز، مثّل القوى، ارسم المنحنى؛ فإن visuals لهذا السؤال إلزامية ولا يجوز أن تكون [].
- إذا كان الجواب النهائي للسؤال هو رسم/دارة/مخطط، فالجواب النصي وحده غير كافٍ.
- إذا لم يوجد رسم مطلوب أو مفيد فعلًا أرجع visuals: [].
- لا ترسل SVG أو HTML أو base64 أو رابط صورة.
- أرسل بيانات الرسم فقط ليقوم React برسمها.
- الأنواع المسموحة: circuit, diagram, graph, table.

للـ circuit أو diagram استعمل:
{
  "type": "circuit أو diagram",
  "title": "عنوان الرسم",
  "width": 760,
  "height": 360,
  "elements": [
    {
      "id": "e1",
      "kind": "battery|source|resistor|capacitor|inductor|switch|lamp|ammeter|voltmeter|oscilloscope|motor|mass|spring|pulley|point|terminal|block|label|circle|rectangle|force|vector|arrow",
      "label": "R أو L أو C أو K أو A أو B أو نص قصير",
      "x": 100,
      "y": 120,
      "width": 90,
      "height": 50,
      "orientation": "horizontal أو vertical",
      "direction": "up|down|left|right عند force/vector/arrow",
      "length": 70
    }
  ],
  "connections": [
    {
      "from": "e1",
      "to": "e2",
      "label": "",
      "style": "wire أو arrow أو dashed"
    }
  ],
  "annotations": [
    {"text": "نص قصير", "x": 300, "y": 60}
  ]
}

مهم في الدارات:
- مثّل الملف بـ kind="inductor" وليس مستطيلًا عاديًا.
- مثّل راسم الاهتزاز بـ kind="oscilloscope"، واربطه بالنقطتين المطلوبتين بواسطة connections.
- إذا طلب السؤال تحديد A و B على طرفي عنصر، أضف عنصرين kind="terminal" بالاسمين A و B في الموضع الصحيح.
- يجب أن تكون التوصيلات الفيزيائية منطقية، لا يكفي وضع أسماء العناصر بجانب بعضها.

للـ graph استعمل:
{
  "type": "graph",
  "title": "عنوان المنحنى",
  "x_label": "t (s)",
  "y_label": "U (V)",
  "x_domain": [0, 10],
  "y_domain": [0, 5],
  "series": [
    {
      "id": "s1",
      "label": "U(t)",
      "data": [{"x": 0, "y": 0}, {"x": 1, "y": 1.2}]
    }
  ]
}

للـ table استعمل:
{
  "type": "table",
  "title": "عنوان الجدول",
  "columns": ["الكمية", "0", "1", "2"],
  "rows": [["t(s)", "0", "1", "2"], ["U(V)", "0", "2", "3"]]
}

- استعمل إحداثيات واضحة داخل width/height.
- لا تجعل عنصرين فوق بعضهما.
- في الدارة، اجعل connections تمثل الأسلاك بين العناصر.
""".strip()

    def build_exercise_prompt(
        self,
        *,
        chapter_title: str,
        branch_name: str,
        references: list[dict[str, Any]],
    ) -> tuple[str, str]:
        system_prompt = f"""
أنت أستاذ جزائري متخصص في تصميم تمارين البكالوريا.

مهمتك إنشاء تمرين واحد جديد فقط اعتمادًا على نمط التمارين المرجعية.

قواعد إلزامية:
- أنشئ التمرين فقط ولا تنشئ الحل.
- لا تنسخ تمرينًا مرجعيًا.
- لا تكتف بتغيير الأعداد؛ غيّر المعطيات والسياق مع الحفاظ على المستوى.
- لا تدخل مفاهيم غير موجودة في التمارين المرجعية.
- اجعل الأسئلة مترابطة ومتدرجة وقابلة للحل من المعطيات.
- لا تضع solution أو answer أو final_answer.
- لا تضع axis_tags أو tag أو tags.
- استعمل $...$ للصيغ الرياضية والفيزيائية.
- لا تستعمل Markdown.
- أرجع JSON صالحًا فقط.
- راجع اتساق المعطيات والأسئلة قبل الإخراج.

{self.VISUAL_RULES}
""".strip()

        user_prompt = f"""
الوحدة: {chapter_title}
الشعبة: {branch_name}

تمارين بكالوريا مرجعية:
{json.dumps(references, ensure_ascii=False)}

أنشئ تمرينًا جديدًا وفق هذا الشكل فقط:

{{
  "title": "عنوان التمرين",
  "statement": "نص التمرين والمعطيات الأساسية",
  "statement_sections": [
    {{"type": "given", "text": "جزء من المعطيات"}}
  ],
  "visuals": [],
  "questions": [
    {{
      "id": "q1",
      "display_order": 1,
      "text": "نص السؤال",
      "skill": "المهارة",
      "points": 1,
      "visuals": []
    }}
  ],
  "estimated_points": 5
}}

شروط إضافية:
- أنشئ بين 4 و6 أسئلة.
- اجعل مجموع النقاط قريبًا من 5.
- لا تذكر سنوات أو أكواد التمارين المرجعية.
- لا تضف الحل بأي شكل.
- إذا كان فهم نص التمرين يحتاج دارة أو مخططًا أو منحنى، ضعه في visuals.
""".strip()

        return system_prompt, user_prompt

    def build_solution_prompt(
        self,
        *,
        generated_exercise_id: int,
        exercise: dict[str, Any],
    ) -> tuple[str, str]:
        system_prompt = f"""
أنت أستاذ جزائري متخصص في حل وتصحيح تمارين البكالوريا.

سيعطيك المستخدم تمرينًا واحدًا فقط بصيغة JSON.
مهمتك حل هذا التمرين نفسه فقط.

قواعد إلزامية:
- لا تغيّر نص التمرين أو أسئلته.
- لا تخترع معطيات غير موجودة.
- حل جميع الأسئلة وبنفس ترتيبها.
- استعمل نتائج الأسئلة السابقة عندما يعتمد عليها السؤال التالي.
- اجعل الشرح واضحًا ومناسبًا لتلميذ البكالوريا.
- كل خطوة مفيدة فعلًا ودون تكرار.
- استعمل $...$ لكل الصيغ الرياضية والفيزيائية.
- لا تستعمل Markdown.
- أرجع JSON صالحًا فقط.
- تأكد أن question_id يطابق id الموجود في التمرين حرفيًا.

قاعدة رسم إلزامية جدًا:
- افحص نص كل سؤال قبل حله.
- إذا كان السؤال يطلب رسمًا أو مخططًا أو دارة أو منحنى أو تمثيل قوى أو تحديد موضع جهاز، يجب أن تكون visuals الخاصة بحل هذا السؤال غير فارغة.
- في هذه الحالة لا تعتبر الإجابة مكتملة إذا شرحت الرسم بالكلام فقط.
- ارسم الشكل المطلوب نفسه ببيانات visuals، ثم اشرح باختصار.
- يمكن أيضًا وضع رسم في step.visuals إذا كان الرسم خاصًا بتلك الخطوة.

{self.VISUAL_RULES}
""".strip()

        user_prompt = f"""
هذا هو التمرين المطلوب حله، ولا تعتمد على أي شيء خارجه:

{json.dumps(exercise, ensure_ascii=False)}

أرجع JSON فقط بالشكل التالي:

{{
  "exercise_id": {generated_exercise_id},
  "general_strategy": "خطة مختصرة للحل",
  "questions": [
    {{
      "question_id": "q1",
      "question_text": "نفس نص السؤال",
      "strategy": "طريقة الحل باختصار",
      "visuals": [],
      "steps": [
        {{
          "step_number": 1,
          "title": "عنوان الخطوة",
          "explanation": "شرح واضح ومباشر",
          "latex": "$الصيغة$ أو سلسلة فارغة",
          "visuals": []
        }}
      ],
      "final_answer": "الجواب النهائي",
      "verification": "تحقق مختصر من النتيجة",
      "hints": [],
      "common_mistakes": [],
      "bac_writing": []
    }}
  ],
  "final_verification": {{
    "all_questions_answered": true,
    "mathematical_consistency": "التحقق النهائي",
    "dependency_consistency": "تحقق ترابط النتائج"
  }}
}}

راجع قبل الإرسال: كل سؤال يطلب رسمًا يجب أن يحتوي solution.questions[i].visuals على الرسم فعليًا.
""".strip()

        return system_prompt, user_prompt


    def build_solution_re_explanation_prompt(
        self,
        *,
        exercise_title: str,
        statement: str,
        question: dict[str, Any],
        original_solution: dict[str, Any],
    ) -> tuple[str, str]:
        system_prompt = f"""
أنت أستاذ دعم لتلميذ بكالوريا جزائري شاهد الحل الكامل ثم قال: «لم أفهم الحل».

مهمتك ليست إعطاء تلميح، بل إعادة شرح حل هذا السؤال كاملًا من البداية بطريقة بسيطة جدًا جدًا.

قواعد إلزامية:
- اشرح نفس الحل الموجود، ولا تغيّر السؤال ولا المعطيات.
- لا تفترض أن التلميذ فهم الحل السابق.
- ابدأ بفكرة واحدة قصيرة جدًا توضح لماذا سنستعمل هذه الطريقة.
- ثم أعد الحل كاملًا في خطوات صغيرة ومتسلسلة.
- استعمل بين 2 و7 خطوات حسب حاجة السؤال.
- كل خطوة تشرح شيئًا واحدًا فقط.
- فسّر أي رمز مهم قبل استعماله إذا كان قد يربك التلميذ.
- اجعل الجمل قصيرة وواضحة.
- لا تستعمل لغة نظرية معقدة إذا أمكن شرحها بكلمات أبسط.
- استعمل $...$ للصيغ الرياضية والفيزيائية.
- لا تستعمل Markdown.
- لا تكتب شيئًا خارج JSON.
- حافظ على نفس النتيجة الصحيحة الموجودة في الحل الأصلي.
- إذا كان الحل الأصلي أو السؤال يحتاج رسمًا، أعد رسمًا مبسطًا في visuals؛ لا تكتف بوصف الرسم بالكلام.
- إذا كان الرسم يخص خطوة محددة، يمكن وضعه في step.visuals.

{self.VISUAL_RULES}
""".strip()

        context = {
            "exercise_title": exercise_title,
            "statement": statement,
            "question": question,
            "original_solution": original_solution,
        }

        user_prompt = f"""
هذا هو السؤال والحل الأصلي الذي لم يفهمه التلميذ:

{json.dumps(context, ensure_ascii=False)}

أعد شرح الحل كاملًا وبأبسط طريقة ممكنة.

أرجع JSON فقط بهذا الشكل:
{{
  "question_id": "{question.get('id', '')}",
  "title": "شرح مبسط للحل",
  "simple_idea": "الفكرة الأساسية في جملة أو جملتين بسيطتين جدًا",
  "visuals": [],
  "steps": [
    {{
      "step_number": 1,
      "title": "عنوان بسيط للخطوة",
      "explanation": "شرح بسيط جدًا لهذه الخطوة",
      "latex": "$صيغة قصيرة$ أو سلسلة فارغة",
      "visuals": []
    }}
  ],
  "final_answer": "النتيجة النهائية بشكل واضح"
}}
""".strip()

        return system_prompt, user_prompt
