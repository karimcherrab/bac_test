from __future__ import annotations

import json
from typing import Any


MAX_PREVIOUS_TITLES = 6
MAX_REFERENCES_NORMAL = 3
MAX_REFERENCES_COMPACT = 2


def _json(value: Any) -> str:
    """
    تحويل البيانات إلى JSON صغير لتقليل حجم الـPrompt.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _short_error(
    value: str,
    max_length: int = 500,
) -> str:
    """
    لا نرسل failed_generation كاملًا لأنه قد يكون ضخمًا.
    """
    text = _text(value)

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."


def _build_output_schema(
    *,
    force_graph: bool,
) -> dict[str, Any]:
    """
    إنشاء نموذج JSON برمجيًا بدل كتابته داخل f-string.

    هذا يمنع مشاكل الأقواس ومحارف الهروب.
    """
    return {
        "exercise": {
            "title": "",
            "question": "",
            "skill": "",
            "hints": [
                {
                    "level": 1,
                    "hint": "",
                },
                {
                    "level": 2,
                    "hint": "",
                },
            ],
            "solution": {
                "strategy": "",
                "detailed_explanation": "",
                "steps": [
                    {
                        "order": 1,
                        "title": "حل المطلب 1",
                        "explanation": "",
                        "calculation": "",
                        "result": "",
                    }
                ],
                "final_answer": "",
                "verification": "",
                "common_mistakes": [
                    {
                        "mistake": "",
                        "why_wrong": "",
                        "correction": "",
                    }
                ],
                "alternative_method": "",
                "is_complete": True,
            },
            "requires_graph": force_graph,
            "graph_spec": (
                {
                    "graph_type": "function",
                    "title": "",
                    "expression_python": "",
                    "expression_label": "",
                    "initial_value": 1,
                    "iterations": 6,
                    "x_min": 0,
                    "x_max": 5,
                    "y_min": 0,
                    "y_max": 5,
                    "step": 0.1,
                }
                if force_graph
                else {}
            ),
        }
    }


def build_bac_like_exercise_prompt(
    *,
    axis_title: str,
    axis_tag: str,
    lesson_context: dict[str, Any],
    bac_references: list[dict[str, Any]],
    previous_titles: list[str],
    exercise_number: int,
    compact_mode: bool = False,
    force_graph: bool = False,
    previous_error: str = "",
) -> str:
    """
    إنشاء Prompt لتوليد تمرين قريب من البكالوريا،
    لكنه مقيد بالمحور الحالي فقط.

    compact_mode:
    يستعمل عند إعادة المحاولة لتقليل حجم الـPrompt.
    """
    reference_limit = (
        MAX_REFERENCES_COMPACT
        if compact_mode
        else MAX_REFERENCES_NORMAL
    )

    references = (
        bac_references[:reference_limit]
        if isinstance(bac_references, list)
        else []
    )

    titles = (
        previous_titles[-MAX_PREVIOUS_TITLES:]
        if isinstance(previous_titles, list)
        else []
    )

    output_schema = _build_output_schema(
        force_graph=force_graph,
    )

    if force_graph:
        graph_rules = """
قواعد الرسم:
- هذا المحور بياني، لذلك يجب أن يحتوي السؤال على طلب بياني واضح.
- اجعل requires_graph يساوي true.
- أعد graph_spec كاملًا.
- expression_python يجب أن يكون تعبير Python بدلالة x فقط.
- استعمل ** للقوة، مثل: x**2.
- لا ترسل نقاط المنحنى.
- الخادم هو الذي سيحسب graph_data.
- إذا كان الرسم مخطط سلم، اجعل graph_type يساوي cobweb.
""".strip()
    else:
        graph_rules = """
قواعد الرسم:
- هذا المحور ليس محورًا بيانيًا.
- اجعل requires_graph يساوي false.
- اجعل graph_spec كائنًا فارغًا.
- ممنوع إدخال رسم أو منحنى من محور آخر.
""".strip()

    retry_rules = ""

    if previous_error:
        retry_rules = f"""
تصحيح المحاولة السابقة:
المحاولة السابقة فشلت للسبب التالي:
{_short_error(previous_error)}

أعد إنشاء النتيجة من البداية.
لا تكمل JSON السابق.
تأكد من إغلاق جميع النصوص والقوائم والأقواس.
""".strip()

    compact_rules = ""

    if compact_mode:
        compact_rules = """
هذه محاولة تصحيح مختصرة:
- لا تكتب مقدمات طويلة.
- اجعل strategy في جملتين كحد أقصى.
- اجعل detailed_explanation فقرة قصيرة.
- لا تكرر نفس الحساب داخل أكثر من حقل.
- اجعل explanation لكل خطوة مختصرًا وواضحًا.
- اجعل verification مختصرًا.
""".strip()

    return f"""
أنت أستاذ رياضيات جزائري متخصص في السنة الثالثة ثانوي
ومصحح لامتحان البكالوريا الجزائرية.

مهمتك إنشاء تمرين تدريبي جديد واحد فقط.

رقم التمرين:
{exercise_number}

المحور الوحيد المسموح:
العنوان: {axis_title}
الوسم: {axis_tag}

محتوى المحور المسموح باستعماله:
{_json(lesson_context)}

أسئلة بكالوريا من المحور نفسه:
{_json(references)}

هذه الأسئلة مراجع أسلوبية فقط.
ممنوع نسخ نصها أو أعدادها أو ترتيب مطالبها حرفيًا.

عناوين تمارين سابقة ممنوع تكرارها:
{_json(titles)}

قواعد حصر التمرين في المحور:
1. يجب أن ينتمي السؤال كاملًا إلى المحور الحالي فقط.
2. يجب أن ينتمي كل مطلب فرعي إلى المحور نفسه.
3. ممنوع استعمال مفهوم من محور آخر.
4. ممنوع إضافة نهاية أو محدودية أو استدلال بالتراجع
   عندما لا تكون موجودة في المحور الحالي.
5. استعمل فقط القواعد والطرق الموجودة في lesson_context.
6. المراجع لا تضيف معرفة جديدة؛ تستعمل فقط لفهم أسلوب البكالوريا.
7. إذا احتجت مفهومًا غير موجود في المحور، غيّر السؤال بدل استعماله.

قواعد إنشاء السؤال:
1. أنشئ وضعية جديدة بأعداد وعلاقات جديدة.
2. اجعل المستوى قريبًا من البكالوريا من حيث الصياغة والتنظيم.
3. لا تجعل التمرين معقدًا أو جامعيًا.
4. تجنب الحسابات الطويلة والكسور الصعبة دون ضرورة.
5. اجعل السؤال مناسبًا للتدريب والفهم.
6. استعمل من مطلب واحد إلى أربعة مطالب حسب حاجة المحور.
7. لا تضف مطالب فقط لزيادة طول التمرين.
8. ضع جميع المعطيات الضرورية داخل question.
9. يجب أن يكون السؤال مستقلًا وقابلًا للحل وحده.
10. رقّم المطالب بوضوح: 1)، 2)، 3).
11. لا تذكر السنة المرجعية.
12. لا تذكر أنك استعملت ذكاءً اصطناعيًا.

قواعد الحل:
1. حل جميع المطالب بالترتيب نفسه.
2. اشرح الحل لتلميذ ضعيف المستوى.
3. قبل استعمال قاعدة، اذكرها واشرح سبب استعمالها.
4. لا تقفز بين نتيجتين.
5. اكتب التحويلات الجبرية المهمة خطوة خطوة.
6. لا يوجد عدد ثابت لخطوات الحل.
7. استعمل عدد الخطوات الضروري لفهم الحل.
8. لا تختصر خطوة مهمة.
9. لا تقسّم عملية بسيطة إلى خطوات كثيرة دون حاجة.
10. كل خطوة تحتوي:
    - title
    - explanation
    - calculation
    - result
11. explanation يشرح ماذا نفعل ولماذا.
12. calculation يحتوي الحساب بالتفصيل.
13. result يحتوي نتيجة الخطوة.
14. final_answer يلخص جواب جميع المطالب.
15. verification يتحقق من النتائج بطريقة بسيطة.
16. أضف تلميحًا أو تلميحين أو ثلاثة حسب الحاجة.
17. الأخطاء الشائعة اختيارية.
18. alternative_method اختياري.
19. اجعل is_complete يساوي true بعد حل جميع المطالب.

قواعد الرياضيات داخل JSON:
1. استعمل علامة الدولار لعرض الرياضيات.
2. مثال صحيح: $u_n = 3n + 2$.
3. مثال صحيح: $u_{{n+1}} - u_n$.
4. تجنب استعمال الأقواس من النوع backslash-parenthesis.
5. ممنوع استعمال backslash-square-bracket.
6. تجنب frac عندما يمكن كتابة الكسر بهذه الصورة:
   $(3n+2)/(n+2)$.
7. لا تكرر الشرطة المائلة backslash.
8. اجعل calculation مقسمًا إلى جمل قصيرة.
9. استعمل newline العادي عند الحاجة، دون إفراط.

{graph_rules}

{compact_rules}

{retry_rules}

قواعد JSON:
1. أعد JSON صالحًا فقط.
2. لا تستعمل Markdown.
3. لا تستعمل code fences.
4. لا تكتب أي نص قبل JSON أو بعده.
5. استعمل علامات اقتباس مزدوجة.
6. لا تضع فاصلة بعد آخر عنصر.
7. أغلق جميع النصوص والقوائم والكائنات.
8. لا تبدأ قيمة نصية ثم تتركها غير مكتملة.
9. لا تضف مفاتيح غير موجودة في النموذج المطلوب.

النموذج المطلوب:
{_json(output_schema)}
""".strip()


class ExercisePromptBuilder:
    """
    دعم للكود القديم.

    الأفضل استعمال build_bac_like_exercise_prompt،
    لكن هذه الفئة تبقى لتجنب كسر الاستدعاءات القديمة.
    """

    @staticmethod
    def build(
        axis,
        difficulty: str = "medium",
        exercise_type: str = "bac",
        skill: str = "",
        include_solution: bool = True,
    ) -> str:
        lesson_context = (
            axis.content
            if isinstance(axis.content, dict)
            else {
                "title": axis.title,
                "content": _text(axis.content),
            }
        )

        skill_text = (
            _text(skill)
            or "اختر مهارة من المحور الحالي فقط."
        )

        schema = _build_output_schema(
            force_graph=False,
        )

        solution_rule = (
            """
أنشئ حلًا كاملًا.
اشرح جميع الخطوات حسب حاجة التمرين.
لا تفرض عددًا ثابتًا للخطوات.
"""
            if include_solution
            else
            """
لا تنشئ حلًا.
اجعل solution كائنًا فارغًا.
"""
        )

        return f"""
أنت أستاذ رياضيات جزائري.

أنشئ تمرينًا واحدًا فقط من المحور الحالي.

المحور:
- id: {axis.id}
- tag: {axis.tag}
- title: {axis.title}

محتوى المحور:
{_json(lesson_context)}

الصعوبة المطلوبة:
{difficulty}

نوع التمرين:
{exercise_type}

المهارة:
{skill_text}

القواعد:
- لا تستعمل أي مفهوم خارج المحور الحالي.
- اجعل التمرين بسيطًا وقريبًا من أسلوب البكالوريا.
- لا تستعمل حسابات معقدة.
- اجعل السؤال مستقلًا.
- استعمل $...$ للتعبيرات الرياضية.
- لا تستعمل Markdown.
- أعد JSON صالحًا فقط.

{solution_rule}

النموذج:
{_json(schema)}
""".strip()