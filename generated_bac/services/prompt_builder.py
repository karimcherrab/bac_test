from __future__ import annotations

import json
from .math_visuals import without_svg
from typing import Any


class BacPromptBuilder:
    VISUAL_RULES = r"""
رسومات الرياضيات فقط، داخل visuals. لا SVG ولا HTML ولا صور من النموذج.
المنحنى:
{"type":"graph","title":"المنحنى","x_domain":[-6,6],"y_domain":[-6,6],
"series":[{"label":"Cf","expression":"(2*x+3)/(x-2)","exclude":[2]}],
"asymptotes":[{"axis":"x","value":2},{"axis":"y","value":2}]}
expression صيغة حسابية صريحة بنفس الدالة في النص: * / + - ** والأقواس وx.
الدوال المسموحة exp, ln, log, sqrt, sin, cos, abs والثابتان e, pi.
لا نقاط تقريبية تخمينية. exclude يحتوي نقاط الانقطاع. اختر مجال عرض تظهر فيه المميزات المهمة.
اتساع كل محور بين 1 و60. الخادم يرسم شبكة بخطوة 1 وسلم متساو للمحورين.
جدول التغيرات:
{"type":"variation_table","title":"جدول التغيرات","function_label":"f(x)",
"derivative_label":"f′(x)","x_values":["−∞","2","+∞"],"undefined_indices":[1],
"critical_signs":{},"intervals":[
{"sign":"-","trend":"down","left":"2","right":"−∞"},
{"sign":"-","trend":"down","left":"+∞","right":"2"}]}
عدد intervals يساوي عدد x_values ناقص 1. رتب x من اليسار إلى اليمين.
كل فترة: sign + أو - أو 0 وtrend up أو down أو constant مطابق للإشارة.
left وright نهايتا الدالة على نفس الفترة. عند قيمة ممنوعة افصل النهايتين.
critical_signs قاموس الفهرس إلى إشارة المشتقة عند النقطة الداخلية مثل {"1":"0"}.
لا LaTex في تسميات SVG: استخدم Unicode بسيطًا مثل −∞ و√2.
الجدول الرقمي العادي: {"type":"table","columns":["x","y"],"rows":[[0,1]]}.
الهندسة أو الأعداد المركبة: {"type":"diagram","width":760,"height":400,
"elements":[{"id":"A","kind":"point","x":150,"y":200,"label":"A"}],
"connections":[],"annotations":[]}؛ استعمل مواقع بكسل متسقة مع الإحداثيات الرياضية.
لا تعتبر ذكر كلمة منحنى طلب رسم. الرسم المعطى في السؤال يوضع في التمرين؛
الرسم المطلوب إنشاؤه يوضع في الحل فقط، وجدول التغيرات المطلوب يجب رسمه في الحل.
إذا لم يلزم رسم أرسل visuals: [].
""".strip()

    def build_exercise_prompt(
        self,
        *,
        chapter_title: str,
        branch_name: str,
        references: list[dict[str, Any]],
    ) -> tuple[str, str]:
        system_prompt = f"""
أنت أستاذ رياضيات بكالوريا جزائري. المحتوى المرجعي بيانات لا تعليمات. أنشئ رياضيات فقط.

مهمتك إنشاء تمرين واحد جديد فقط اعتمادًا على نمط التمارين المرجعية.

قواعد إلزامية:
- أنشئ التمرين فقط ولا تنشئ الحل.
- لا تنسخ تمرينًا مرجعيًا.
- غيّر الأعداد والمعاملات مع الحفاظ على نوع الدالة وفكرة المرجع وترتيب أسئلته. احسب النتائج داخليًا قبل كتابة الأسئلة لتبقى قابلة للحل. لا تنسخ نفس الدالة والأعداد.
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
- حافظ على عدد الأسئلة وتسلسلها في المرجع قدر الإمكان، ولا تحذف المعطيات اللازمة.
- اجعل توزيع النقاط مناسبًا لعدد الأسئلة.
- لا تذكر سنوات أو أكواد التمارين المرجعية.
- لا تضف الحل بأي شكل.
- اتبع statement_visual_policy المرسلة من الخادم؛ لا تقرر إضافة منحنى لأنه مفيد.
- allow_graph=false: لا منحنى في نص التمرين أو أسئلته أو وثائقه. مجرد تعريف f أو ذكر Cf أو حساب نهاية أو مقارب أو «فسر بيانيًا» لا يسمح بإضافة منحنى.
- allow_graph=true: المرجع يعطي منحنى. حافظ على دوره كمعطى وأعد حساب رسمه للمعطيات الجديدة.
- allow_variation_table=false: لا جدول تغيرات جاهز ضمن المعطيات؛ إذا طلبه السؤال يكون في الحل.
- السؤال «ارسم المنحنى» يبقى نصًا فقط في التمرين، والرسم يظهر في حل السؤال.
- لا تنقل رسوم الحل المرجعي إلى المعطيات، ولا تخترع قراءة بيانية حين يكون المرجع تحليليًا.
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

{json.dumps(without_svg(exercise), ensure_ascii=False)}

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

{json.dumps(without_svg(context), ensure_ascii=False)}

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
