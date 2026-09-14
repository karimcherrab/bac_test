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


def _short_error(value: str, max_length: int = 700) -> str:
    text = _text(value)
    return text if len(text) <= max_length else text[:max_length].rstrip() + "..."


def _output_schema(*, force_graph: bool) -> dict[str, Any]:
    return {
        "exercise": {
            "title": "",
            "question": "",
            "skill": "",
            "document_references": [
                {"id": "document_01", "path": "مسار من القائمة المسموحة حرفيا", "title": "", "placement": "statement"}
            ],
            "hints": [{"level": 1, "hint": ""}, {"level": 2, "hint": ""}],
            "visuals": [],
            "solution": {
                "strategy": "",
                "detailed_explanation": "",
                "steps": [{"order": 1, "title": "الملاحظة", "explanation": "", "calculation": "", "result": ""}],
                "final_answer": "",
                "verification": "",
                "common_mistakes": [{"mistake": "", "why_wrong": "", "correction": ""}],
                "alternative_method": "",
                "is_complete": True,
            },
            "requires_graph": force_graph,
            "graph_spec": {
                "graph_type": "function", "title": "", "expression_python": "", "expression_label": "",
                "initial_value": 1, "iterations": 6, "x_min": 0, "x_max": 5, "y_min": 0, "y_max": 5, "step": 0.1,
            } if force_graph else {},
        }
    }


def _subject_rules(subject_kind: str, has_documents: bool) -> str:
    if subject_kind == "natural_sciences":
        document_rule = "يجب استعمال وثيقة واحدة صالحة على الأقل من القائمة المسموحة." if has_documents else "لا توجد وثيقة مسترجعة؛ أنشئ تمرينا نصيا قصيرا ولا تخترع صورة أو جدولا تجريبيا."
        return f"""
قواعد إلزامية خاصة بعلوم الطبيعة والحياة:
- أنت أستاذ علوم جزائري ومصحح بكالوريا، وتبني وضعية استدلالية لا سؤال حفظ مباشر.
- {document_rule}
- اتبع التسلسل: سياق علمي قصير ← تقديم الوثيقة ← مطالب تحليل/تفسير/استنتاج ← تركيب أو نص علمي عند الحاجة.
- لا تنسخ نص مرجع بكالوريا، لكن حافظ على مستوى لغته وأفعاله المنهجية.
- كل معلومة عددية أو منحنى أو جدول أو رسم يجب أن يكون ظاهرًا في الوثيقة المستعملة؛ ممنوع اختراع قيمة غير موجودة.
- لا تعدّل الصورة ولا مسارها ولا تسمياتها ولا اتجاه الأسهم ولا القيم.
- لا تستعمل وثيقة موسومة solution_reference_only، ولا صورة حل، ولا مخطط تصحيح.
- احترم answer_invariants حرفيًا، ولا تقع في forbidden_changes.
- اذكر داخل question: «باستغلال الوثيقة...» واجعل كل مطلب قابلا للحل منها مع معارف المحور.
- الحل يكتب بالطريقة: ملاحظة دقيقة من الوثيقة ← تفسير علمي ← استنتاج يجيب عن المطلوب.
- إذا طلب نص علمي، اجعله مقدمة وعرضًا وخاتمة بلغة بسيطة ودقيقة.
- document_references تحتوي فقط id/path/title من قائمة الوثائق المسموحة وplacement="statement".
- لا تنشئ SVG أو base64 أو رابطًا أو path جديدًا، واجعل visuals=[] لأن الوثائق صور جاهزة يعرضها React.
""".strip()
    if subject_kind == "physics":
        return """
قواعد الفيزياء: حافظ على الوحدات والرموز. يمكن استعمال table/circuit/diagram المولدة بنيويا، ولا تخترع صورة. استعمل LaTeX صحيحا.
""".strip()
    return """
قواعد الرياضيات: لا تستعمل circuit. استعمل graph_spec فقط للمحور البياني المفروض، ولا ترسل نقاط منحنى يدويا.
""".strip()


def build_bac_like_exercise_prompt(
    *, subject_kind: str, subject_name: str, axis_title: str, axis_tag: str,
    lesson_context: dict[str, Any], bac_references: list[dict[str, Any]],
    previous_titles: list[str], exercise_number: int, compact_mode: bool = False,
    force_graph: bool = False, previous_error: str = "", allowed_documents: list[dict[str, Any]] | None = None,
) -> str:
    limit = MAX_REFERENCES_COMPACT if compact_mode else MAX_REFERENCES_NORMAL
    references = bac_references[:limit] if isinstance(bac_references, list) else []
    references_for_prompt = []
    for reference in references:
        if not isinstance(reference, dict):
            continue
        compact_reference = {key: value for key, value in reference.items() if key != "documents"}
        compact_reference["available_document_ids"] = [
            _text(item.get("id")) for item in reference.get("documents", [])[:4]
            if isinstance(item, dict)
        ]
        references_for_prompt.append(compact_reference)
    titles = previous_titles[-MAX_PREVIOUS_TITLES:] if isinstance(previous_titles, list) else []
    documents = allowed_documents if isinstance(allowed_documents, list) else []
    retry = f"المحاولة السابقة رُفضت بسبب: {_short_error(previous_error)}\nصحح السبب ولا تكرر الإخراج السابق." if previous_error else ""
    compact = "اختصر الشرح دون حذف أي مطلب أو دليل من الوثيقة." if compact_mode else ""

    return f"""
أنت أستاذ جزائري خبير في بناء تمارين البكالوريا لمادة {subject_name}.
أنشئ تمرينًا تدريبيًا جديدًا واحدًا فقط داخل المحور المحدد، بصيغة JSON فقط.

المادة الداخلية: {subject_kind}
رقم النسخة: {exercise_number}
المحور: {axis_title}
وسم المحور: {axis_tag}

محتوى الدرس المسموح، وهو المصدر العلمي الأول:
{_json(lesson_context)}

مراجع بكالوريا للاستلهام في البنية والمنهجية فقط، لا للنسخ:
{_json(references_for_prompt)}

الوثائق العلمية المسموح استعمالها حصرا:
{_json(documents)}

عناوين سابقة ممنوع تكرارها:
{_json(titles)}

قواعد عامة إلزامية:
1. لا تدخل أي مفهوم خارج المحور ومحتوى الدرس.
2. لا تنسخ نص المرجع أو أرقامه أو ترتيب مطالبه حرفيًا.
3. أنشئ سياقًا جديدًا، لكن لا تغيّر حقائق الوثيقة المستعملة.
4. من مطلبين إلى أربعة، مرتبة 1)، 2)، 3)، وبأفعال بكالوريا واضحة.
5. ضع كل المعطيات الضرورية في السؤال أو في الوثيقة المشار إليها.
6. حل جميع المطالب بالترتيب، وبأسلوب يفهمه التلميذ الضعيف.
7. كل خطوة تحتوي title وexplanation وcalculation وresult؛ اترك calculation="" إن لم يوجد حساب.
8. final_answer يجمع الأجوبة النهائية، وverification يراجع التوافق مع الوثيقة.
9. التلميحات متدرجة ولا تكشف الجواب مباشرة.
10. ممنوع Markdown وcode fences وأي نص خارج JSON.

{_subject_rules(subject_kind, bool(documents))}

قواعد الرسم البياني:
- requires_graph={str(force_graph).lower()}.
- إن كان false أرسل graph_spec={{}}.
- علوم الطبيعة لا تستعمل graph_spec لرسم وثيقة؛ تستعمل document_references فقط.

{compact}
{retry}

أعد هذا النموذج وحده مع ملء القيم:
{_json(_output_schema(force_graph=force_graph))}
""".strip()


class ExercisePromptBuilder:
    @staticmethod
    def build(axis, difficulty: str = "medium", exercise_type: str = "bac", skill: str = "", include_solution: bool = True) -> str:
        subject = getattr(getattr(axis, "chapter", None), "subject", None)
        subject_name = _text(getattr(subject, "name", "")) or "المادة"
        source = f"{getattr(subject, 'code', '')} {subject_name}".lower()
        if any(x in source for x in ("science", "sciences", "svt", "طبيعة", "علوم")):
            kind = "natural_sciences"
        elif any(x in source for x in ("phys", "physics", "فيزياء")):
            kind = "physics"
        else:
            kind = "math"
        content = axis.content if isinstance(axis.content, dict) else {"title": axis.title, "content": _text(axis.content)}
        return build_bac_like_exercise_prompt(subject_kind=kind, subject_name=subject_name, axis_title=axis.title, axis_tag=axis.tag, lesson_context=content, bac_references=[], previous_titles=[], exercise_number=1, force_graph=False, allowed_documents=[])
