from dataclasses import dataclass

from django.db import transaction

from ..models import StudentMessage, StudentSession
from .context_builder import TutorContextBuilder
from .llm import TutorLLMClient
from .prompt_builder import build_llm_messages, choose_mode, detect_intent


@dataclass
class TutorResult:
    session_id: str
    answer: str
    intent: str
    mode: str
    model: str
    context: dict
    sources: list
    suggestions: list


class TutorOrchestrator:
    def __init__(self, llm_client=None):
        self.llm = llm_client or TutorLLMClient()

    def handle(
        self,
        *,
        question,
        student,
        chapter,
        page_context=None,
        session=None,
    ):
        page_context = page_context or {}

        if session is None:
            session = self._create_session(student=student, chapter=chapter)

        context = TutorContextBuilder(
            student=student,
            chapter=chapter,
            page_context=page_context,
        ).build()

        intent = detect_intent(question, context)
        mode = choose_mode(intent)

        history = list(
            session.messages
            .filter(role__in=["student", "assistant"])
            .order_by("-created_at")[:10]
        )
        history.reverse()

        messages = build_llm_messages(
            question=question,
            context=context,
            history=history,
        )

        answer, model = self.llm.generate(messages)
        sources = self._build_sources(context)
        suggestions = self._build_suggestions(context, intent)

        with transaction.atomic():
            axis_id = (context.get("axis") or {}).get("id")
            snapshot = self._message_context(context)

            StudentMessage.objects.create(
                session=session,
                role=StudentMessage.ROLE_STUDENT,
                content=question,
                intent=intent,
                mode=mode,
                chapter=chapter,
                axis_id=axis_id,
                context_snapshot=snapshot,
                metadata={"source": "lesson_page"},
            )

            StudentMessage.objects.create(
                session=session,
                role=StudentMessage.ROLE_ASSISTANT,
                content=answer,
                intent=intent,
                mode=mode,
                chapter=chapter,
                axis_id=axis_id,
                context_snapshot=snapshot,
                metadata={
                    "model": model,
                    "sources": sources,
                },
            )

            self._update_session(
                session=session,
                question=question,
                answer=answer,
                intent=intent,
                mode=mode,
                model=model,
                context=context,
            )

        return TutorResult(
            session_id=str(session.id),
            answer=answer,
            intent=intent,
            mode=mode,
            model=model,
            context=context,
            sources=sources,
            suggestions=suggestions,
        )

    @staticmethod
    def _create_session(*, student, chapter):
        StudentSession.objects.filter(
            student=student,
            chapter=chapter,
            is_active=True,
        ).update(is_active=False)

        return StudentSession.objects.create(
            student=student,
            chapter=chapter,
            title=f"محادثة: {chapter.title}",
            is_active=True,
        )

    @staticmethod
    def _update_session(*, session, question, answer, intent, mode, model, context):
        axis = context.get("axis") or {}
        exercise = context.get("exercise") or {}
        current_question = context.get("question") or {}
        step = context.get("step") or {}
        learning = context.get("student_learning") or {}
        section = context.get("section") or {}

        session.current_axis_id = axis.get("id")
        session.current_section = str(section.get("id", ""))[:100]

        session.current_exercise_kind = str(exercise.get("kind", ""))[:80]
        session.current_exercise_id = str(exercise.get("id", ""))[:120]
        session.current_exercise_title = str(exercise.get("title", ""))[:255]

        session.current_question_id = str(current_question.get("id", ""))[:150]
        session.current_question_number = str(current_question.get("number", ""))[:50]
        session.current_question_title = str(current_question.get("title", ""))[:255]

        session.current_step_id = str(step.get("id", ""))[:150]
        session.current_step_title = str(step.get("title", ""))[:255]
        session.current_step_type = str(step.get("type", ""))[:100]

        session.current_skill = str(
            current_question.get("skill") or exercise.get("skill") or ""
        )[:150]
        session.current_intent = intent
        session.last_question = question
        session.last_answer = answer
        session.context_snapshot = context
        session.metadata = {
            "model": model,
            "mode": mode,
            "student_level": learning.get("level"),
            "mastery_score": learning.get("mastery_score"),
            "recent_mistakes_count": len(context.get("recent_mistakes") or []),
            "exercise_verified": bool(exercise.get("verified")) if exercise else False,
            "question_verified": bool(current_question.get("verified")) if current_question else False,
            "step_verified": bool(step.get("verified")) if step else False,
        }
        session.is_active = True
        session.save()

    @staticmethod
    def _message_context(context):
        # Snapshot compact mais assez riche pour comprendre les références futures.
        axis = dict(context.get("axis") or {})
        axis.pop("lesson_excerpt", None)
        return {
            "chapter": context.get("chapter"),
            "axis": axis or None,
            "section": context.get("section"),
            "exercise": context.get("exercise"),
            "question": context.get("question"),
            "step": context.get("step"),
            "view_state": context.get("view_state"),
            "selection": context.get("selection"),
            "student_learning": context.get("student_learning"),
            "recent_mistakes": (context.get("recent_mistakes") or [])[:3],
            "recent_confusions": (context.get("recent_confusions") or [])[:3],
        }

    @staticmethod
    def _build_sources(context):
        sources = []
        chapter = context.get("chapter") or {}
        axis = context.get("axis") or {}
        exercise = context.get("exercise") or {}
        current_question = context.get("question") or {}
        step = context.get("step") or {}

        if axis:
            sources.append({
                "type": "lesson_axis",
                "id": axis.get("id"),
                "tag": axis.get("tag", ""),
                "title": axis.get("title", ""),
            })

        if exercise:
            sources.append({
                "type": exercise.get("kind", "exercise"),
                "id": exercise.get("id") or None,
                "title": exercise.get("title", ""),
                "verified": exercise.get("verified", False),
            })

        if current_question:
            sources.append({
                "type": "current_question",
                "id": current_question.get("id") or None,
                "title": current_question.get("title", ""),
                "verified": current_question.get("verified", False),
            })

        if step:
            sources.append({
                "type": "current_solution_step",
                "id": step.get("id") or None,
                "title": step.get("title", ""),
                "verified": step.get("verified", False),
            })

        if context.get("recent_mistakes"):
            sources.append({
                "type": "student_recent_mistakes",
                "title": f"أخطاء حديثة في {axis.get('title') or chapter.get('title', '')}",
            })

        return sources

    @staticmethod
    def _build_suggestions(context, intent):
        suggestions = []
        if context.get("step") or context.get("selection"):
            suggestions.append("اشرح لي هذه الخطوة بطريقة أبسط")
        if context.get("question"):
            suggestions.append("ما الفكرة المطلوبة في هذا السؤال؟")
        if context.get("exercise"):
            suggestions.append("أعطني تلميحًا فقط")
        if context.get("recent_mistakes"):
            suggestions.append("هل أكرر نفس الخطأ السابق؟")
        if intent != "quiz":
            suggestions.append("اختبرني بسؤال قصير")
        return suggestions[:4]
