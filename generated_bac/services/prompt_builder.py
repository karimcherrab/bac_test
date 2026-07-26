import json
from typing import Any


class BacPromptBuilder:
    def build_exercise_prompt(
        self,
        *,
        chapter_title: str,
        branch_name: str,
        references: list[dict[str, Any]],
    ) -> tuple[str, str]:
        system_prompt = """
أنت أستاذ ومصمم تمارين للبكالوريا الجزائرية.

ستحصل على مجموعة تمارين بكالوريا حقيقية تنتمي إلى:
- نفس الوحدة.
- نفس الشعبة.

مهمتك:
إنشاء تمرين جديد يشبه هذه التمارين في الأسلوب،
البنية، مستوى الصعوبة، ترابط الأسئلة وطريقة الصياغة.

قواعد إلزامية:
1. أنشئ التمرين فقط، ولا تنشئ الحل.
2. لا تنسخ أي تمرين مرجعي.
3. لا تغيّر الأعداد فقط؛ يجب أن تكون الفكرة والمعطيات جديدة.
4. استعمل فقط المفاهيم الظاهرة في التمارين المرجعية.
5. يجب أن تكون كل الأسئلة قابلة للحل من المعطيات.
6. الأسئلة مترابطة ومتدرجة مثل البكالوريا.
7. لا تضع solution أو answer داخل الأسئلة.
8.اذا كان نص تمرين يحتاج منحنى بياني قم برسمه لأعضره في react
9. استعمل LaTeX داخل \\(...\\) أو \\[...\\].
10. أرجع JSON فقط، بدون Markdown.
11. راجع الاتساق الرياضي قبل الإخراج.
""".strip()

        user_prompt = f"""
الوحدة:
{chapter_title}

الشعبة:
{branch_name}

تمارين البكالوريا المرجعية:
{json.dumps(references, ensure_ascii=False)}

أنشئ تمرينًا جديدًا بالكامل وفق هذا الشكل:

{{
  "title": "عنوان التمرين",
  "statement": "المعطيات الأساسية فقط",
  "statement_sections": [
    {{
      "type": "given أو definition أو context",
      "text": "النص"
    }}
  ],
  "questions": [
    {{
      "id": "q1",
      "display_order": 1,
      "text": "نص السؤال",
      "axis_tags": ["tag"],
      "skill": "المهارة",
      "points": 1
    }}
  ],
  "axis_tags": ["جميع المحاور المستعملة"],
  "estimated_points": 5,
  "originality_check": "شرح مختصر يؤكد أن التمرين جديد",
  "coherence_check": "شرح مختصر يؤكد أن الأسئلة قابلة للحل"
}}

شروط إضافية:
- أنشئ بين 4 و6 أسئلة.
- اجعل مجموع النقاط قريبًا من 5.
- لا تذكر السنوات أو أكواد التمارين المرجعية.
- لا تضف الحل.
""".strip()

        return system_prompt, user_prompt

    def build_solution_prompt(
        self,
        *,
        generated_exercise_id: int,
        chapter_title: str,
        branch_name: str,
        exercise: dict[str, Any],
        solution_style_references: list[dict[str, Any]],
    ) -> tuple[str, str]:
        system_prompt = """
أنت أستاذ رياضيات جزائري متخصص في حل وتصحيح
تمارين البكالوريا.

مهمتك حل التمرين المعطى فقط.

قواعد إلزامية:
1. لا تغير التمرين ولا أسئلته.
2. حل جميع الأسئلة بالترتيب.
3. قدم حلًا مفصلًا لتلميذ ضعيف المستوى.
4. كل خطوة تحتوي عنوانًا وشرحًا وصيغة LaTeX عند الحاجة.
5. إذا لم توجد صيغة، اجعل latex سلسلة فارغة.
6. استعمل النتائج السابقة عندما يعتمد عليها السؤال.
7. أضف تلميحات وأخطاء شائعة وكتابة نموذجية للبكالوريا.
8. تحقق من النتائج رياضيًا.
9. لا تضع graph_data.
10. أرجع JSON فقط، بدون Markdown.
""".strip()

        user_prompt = f"""
معرف التمرين:
{generated_exercise_id}

الوحدة:
{chapter_title}

الشعبة:
{branch_name}

التمرين:
{json.dumps(exercise, ensure_ascii=False)}

# أمثلة مختصرة لطريقة تنظيم حلول البكالوريا:
# {json.dumps(solution_style_references, ensure_ascii=False)}

أرجع الحل وفق هذا الشكل:

{{
  "exercise_id": {generated_exercise_id},
  "general_strategy": "الخطة العامة",
  "questions": [
    {{
      "question_id": "q1",
      "question_text": "نص السؤال",
      "strategy": "طريقة الحل",
      "steps": [
        {{
          "step_number": 1,
          "title": "عنوان الخطوة",
          "explanation": "شرح واضح",
          "latex": "الصيغة أو سلسلة فارغة"
        }}
      ],
      "final_answer": "الجواب النهائي",
      "verification": "التحقق",
      "hints": ["تلميح"],
      "common_mistakes": ["خطأ شائع"],
      "bac_writing": ["صياغة نموذجية"]
    }}
  ],
  "final_verification": {{
    "all_questions_answered": true,
    "mathematical_consistency": "نتيجة التحقق",
    "dependency_consistency": "نتيجة تحقق ترابط الأسئلة"
  }}
}}
""".strip()

        return system_prompt, user_prompt
