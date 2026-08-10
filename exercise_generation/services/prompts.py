from __future__ import annotations

import json
from typing import Any

MAX_PREVIOUS_TITLES = 6
MAX_REFERENCES_NORMAL = 3
MAX_REFERENCES_COMPACT = 2


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _short_error(value: str, max_length: int = 500) -> str:
    text = _text(value)
    return text if len(text) <= max_length else text[:max_length].rstrip() + "..."


def _visual_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "table",
            "title": "",
            "headers": [""],
            "rows": [[""]],
            "caption": "",
        },
        {
            "type": "circuit",
            "title": "",
            "width": 720,
            "height": 360,
            "components": [
                {
                    "id": "R1",
                    "type": "resistor",
                    "label": "$R$",
                    "value": "$100\\,\\Omega$",
                    "x": 300,
                    "y": 120,
                    "rotation": 0,
                }
            ],
            "wires": [
                {"x1": 100, "y1": 120, "x2": 250, "y2": 120, "label": ""}
            ],
            "caption": "",
        },
        {
            "type": "diagram",
            "title": "",
            "width": 720,
            "height": 360,
            "elements": [
                {
                    "type": "arrow",
                    "x1": 120,
                    "y1": 240,
                    "x2": 300,
                    "y2": 120,
                    "label": "$\\vec{F}$",
                }
            ],
            "caption": "",
        },
    ]


def _build_output_schema(*, force_graph: bool) -> dict[str, Any]:
    return {
        "exercise": {
            "title": "",
            "question": "",
            "skill": "",
            "hints": [
                {"level": 1, "hint": ""},
                {"level": 2, "hint": ""},
            ],
            "visuals": [],
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
                    {"mistake": "", "why_wrong": "", "correction": ""}
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


def _subject_rules(subject_kind: str) -> str:
    if subject_kind == "physics":
        return """
قواعد خاصة بالفيزياء:
- أنت أستاذ فيزياء جزائري للسنة الثالثة ثانوي.
- حافظ على الوحدات الدولية والرموز الفيزيائية الصحيحة.
- عندما يحتاج التمرين جدول قياسات، أضف visual من type=table بدل كتابة الجدول كسطر نصي طويل.
- عندما يحتاج التمرين دارة كهربائية، أضف visual من type=circuit ببنية components وwires.
- عندما يحتاج التمرين مخططًا ميكانيكيًا أو شعاعًا أو مسارًا، أضف visual من type=diagram.
- لا تضف أي visual إن كان التمرين مفهومًا وقابلًا للحل دون شكل.
- يجب أن يحتوي نص question على إحالة واضحة مثل: «اعتمادًا على الجدول الآتي» أو «لدينا الدارة المبينة» عندما يوجد visual.
- visual جزء من معطيات التمرين، وليس جزءًا من الحل.
- لا ترسل SVG أو HTML أو base64 أو صورة. أرسل بيانات JSON فقط ليقوم React بالرسم.
- في circuit استعمل فقط الأنواع: resistor, capacitor, battery, generator, switch, lamp, ammeter, voltmeter, coil, node.
- إحداثيات circuit وdiagram تكون داخل width/height وبقيم موجبة.
- استعمل LaTeX داخل labels والقيم، مثل $U_R$ و$R=100\\,\\Omega$.
""".strip()

    return """
قواعد خاصة بالرياضيات:
- أنت أستاذ رياضيات جزائري للسنة الثالثة ثانوي.
- لا تضف visual من نوع circuit.
- يمكن استعمال visual من type=table فقط إذا كانت المعطيات جدوليّة فعلًا.
- الرسوم البيانية الرياضية تبقى عبر requires_graph وgraph_spec لكي يحسبها الخادم بدقة.
- لا ترسل نقاط منحنى يدويًا داخل visuals.
""".strip()


def build_bac_like_exercise_prompt(
    *,
    subject_kind: str,
    subject_name: str,
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
    reference_limit = MAX_REFERENCES_COMPACT if compact_mode else MAX_REFERENCES_NORMAL
    references = bac_references[:reference_limit] if isinstance(bac_references, list) else []
    titles = previous_titles[-MAX_PREVIOUS_TITLES:] if isinstance(previous_titles, list) else []
    output_schema = _build_output_schema(force_graph=force_graph)

    if force_graph:
        graph_rules = """
قواعد الرسم البياني الرياضي:
- هذا المحور بياني، لذلك يجب أن يحتوي السؤال على طلب بياني واضح.
- اجعل requires_graph=true وأعد graph_spec كاملًا.
- expression_python تعبير Python بدلالة x فقط، واستعمل ** للقوة.
- لا ترسل نقاط المنحنى؛ الخادم يحسب graph_data.
- إذا كان الرسم مخطط سلم اجعل graph_type=cobweb.
""".strip()
    else:
        graph_rules = """
قواعد graph_spec:
- اجعل requires_graph=false وgraph_spec={} ما لم يكن هذا محور رياضيات بيانيًا مفروضًا من الخادم.
- الرسومات الفيزيائية لا تستعمل graph_spec؛ استعمل visuals بدلًا منه.
""".strip()

    retry_rules = ""
    if previous_error:
        retry_rules = f"""
تصحيح المحاولة السابقة:
{_short_error(previous_error)}
أعد إنشاء النتيجة من البداية، ولا تكمل JSON السابق، وأغلق كل النصوص والقوائم والأقواس.
""".strip()

    compact_rules = ""
    if compact_mode:
        compact_rules = """
هذه محاولة تصحيح مختصرة:
- اختصر strategy وdetailed_explanation.
- لا تكرر الحساب نفسه في أكثر من حقل.
- اجعل كل خطوة قصيرة وكاملة.
""".strip()

    return f"""
أنت أستاذ جزائري متخصص في مادة {subject_name or ('الفيزياء' if subject_kind == 'physics' else 'الرياضيات')} للسنة الثالثة ثانوي ومصحح للبكالوريا الجزائرية.

مهمتك إنشاء تمرين تدريبي جديد واحد فقط، قريب من أسلوب البكالوريا، ومحصور في المحور الحالي.

رقم التمرين: {exercise_number}
المادة: {subject_name}
نوع المادة الداخلي: {subject_kind}
المحور الوحيد المسموح:
- العنوان: {axis_title}
- الوسم: {axis_tag}

محتوى المحور المسموح:
{_json(lesson_context)}

أسئلة بكالوريا من المحور نفسه، للاستلهام في الأسلوب فقط:
{_json(references)}

ممنوع نسخ نص أو أعداد أو ترتيب مطالب أي مرجع حرفيًا.
عناوين تمارين سابقة ممنوع تكرارها:
{_json(titles)}

قواعد الحصر في المحور:
1. السؤال وكل مطالبه من المحور الحالي فقط.
2. لا تدخل مفهومًا من محور آخر.
3. استعمل فقط القواعد والطرق الموجودة في lesson_context.
4. المرجع أسلوبي فقط ولا يضيف معرفة جديدة.
5. إذا احتجت مفهومًا غير موجود، غيّر السؤال.

قواعد السؤال:
1. أنشئ وضعية جديدة بأعداد وعلاقات جديدة.
2. من مطلب واحد إلى أربعة حسب الحاجة فقط.
3. ضع كل المعطيات الضرورية في question أو visuals.
4. رقّم المطالب بوضوح: 1)، 2)، 3).
5. لا تذكر السنة المرجعية ولا الذكاء الاصطناعي.
6. الحسابات معقولة ومناسبة للبكالوريا وليست جامعية.

قواعد الحل:
1. حل جميع المطالب بالترتيب نفسه.
2. اشرح لتلميذ ضعيف المستوى دون قفزات.
3. كل خطوة تحتوي title وexplanation وcalculation وresult.
4. calculation يحتوي الحساب الضروري فقط.
5. final_answer يلخص جميع الأجوبة.
6. verification مختصر ومفيد.
7. التلميحات متدرجة ولا تكشف الحل مباشرة.
8. is_complete=true بعد حل جميع المطالب.

قواعد LaTeX داخل JSON:
1. استعمل $...$ لكل تعبير رياضي أو فيزيائي.
2. أمثلة: $u_n=3n+2$، $U_R=R\\,I$، $\\tau=RC$، $v=\\Delta x/\\Delta t$.
3. استعمل أوامر LaTeX القياسية: \\frac, \\sqrt, \\times, \\mathrm, \\vec عند الحاجة.
4. لأن النص داخل JSON، يجب أن تكون الشرطة المائلة مهروبة بشكل JSON صحيح.
5. لا تستعمل Markdown ولا code fences.

{_subject_rules(subject_kind)}

قواعد visuals:
- القيمة الافتراضية visuals=[] إذا لم يحتج السؤال شكلاً.
- الأنواع المدعومة فقط: table, circuit, diagram.
- لا تضع visual فارغًا.
- لا تستخدم أي visual للمظهر فقط؛ يجب أن يكون جزءًا مفيدًا من معطيات السؤال.
- نموذج الأنواع المتاحة للاستدلال على البنية فقط:
{_json(_visual_schema())}

{graph_rules}
{compact_rules}
{retry_rules}

قواعد JSON:
- أعد JSON صالحًا فقط، بلا Markdown أو نص خارجي.
- استعمل علامات اقتباس مزدوجة وأغلق كل البنى.
- لا تضف مفاتيح خارج النموذج المطلوب.

النموذج المطلوب:
{_json(output_schema)}
""".strip()


class ExercisePromptBuilder:
    @staticmethod
    def build(axis, difficulty: str = "medium", exercise_type: str = "bac", skill: str = "", include_solution: bool = True) -> str:
        subject = getattr(getattr(axis, "chapter", None), "subject", None)
        subject_name = _text(getattr(subject, "name", "")) or "الرياضيات"
        subject_source = f"{getattr(subject, 'code', '')} {subject_name}".lower()
        subject_kind = "physics" if any(k in subject_source for k in ("phys", "فيزياء", "physics")) else "math"
        lesson_context = axis.content if isinstance(axis.content, dict) else {"title": axis.title, "content": _text(axis.content)}
        return build_bac_like_exercise_prompt(
            subject_kind=subject_kind,
            subject_name=subject_name,
            axis_title=axis.title,
            axis_tag=axis.tag,
            lesson_context=lesson_context,
            bac_references=[],
            previous_titles=[],
            exercise_number=1,
            compact_mode=False,
            force_graph=False,
        )
