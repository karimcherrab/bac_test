# knowledge/tutor/session_manager.py

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from course.models import Axis, Chapter
from knowledge.models import StudentMessage, StudentSession


@dataclass
class SessionContext:
    session: StudentSession
    history: list[StudentMessage]

    last_question: str
    last_answer: str

    current_skill: str
    current_intent: str

    chapter: Chapter | None
    current_axis: Axis | None

    chapter_id: int | None
    chapter_code: str
    chapter_title: str

    axis_id: int | None
    axis_tag: str
    axis_title: str

    metadata: dict


class SessionManager:
    """
    Gestion des sessions et de l'historique du tuteur IA.
    """

    def get_or_create_session(
        self,
        student,
        chapter: Chapter,
        session_id: str | None = None,
        current_axis: Axis | None = None,
        title: str = "",
    ) -> StudentSession:
        """
        Récupère une session existante appartenant à l'étudiant
        ou crée une nouvelle session.

        Une session existante doit appartenir au même chapitre.
        """

        if session_id:
            try:
                session_uuid = UUID(str(session_id))

                session = (
                    StudentSession.objects
                    .select_related(
                        "student",
                        "chapter",
                        "current_axis",
                    )
                    .get(
                        id=session_uuid,
                        student=student,
                    )
                )

                if (
                    session.chapter_id
                    and session.chapter_id != chapter.id
                ):
                    raise ValueError(
                        "هذه الجلسة مرتبطة بفصل آخر. "
                        "أنشئ جلسة جديدة لهذا الفصل."
                    )

                fields_to_update = []

                if session.chapter_id is None:
                    session.chapter = chapter
                    fields_to_update.append("chapter")

                if (
                    current_axis is not None
                    and session.current_axis_id != current_axis.id
                ):
                    self.validate_axis_chapter(
                        axis=current_axis,
                        chapter=chapter,
                    )

                    session.current_axis = current_axis
                    fields_to_update.append("current_axis")

                if not session.is_active:
                    session.is_active = True
                    fields_to_update.append("is_active")

                if fields_to_update:
                    fields_to_update.append("updated_at")

                    session.save(
                        update_fields=fields_to_update,
                    )

                return session

            except StudentSession.DoesNotExist:
                pass

            except (ValueError, TypeError):
                if isinstance(session_id, str):
                    try:
                        UUID(session_id)
                    except ValueError:
                        pass
                    else:
                        raise

        self.validate_axis_chapter(
            axis=current_axis,
            chapter=chapter,
        )

        return StudentSession.objects.create(
            student=student,
            title=title or f"Chat - {chapter.title}",
            chapter=chapter,
            current_axis=current_axis,
            is_active=True,
            metadata={
                "chapter_id": chapter.id,
                "chapter_code": chapter.code,
                "chapter_title": chapter.title,
                "axis_id": (
                    current_axis.id
                    if current_axis
                    else None
                ),
                "axis_tag": (
                    current_axis.tag
                    if current_axis
                    else ""
                ),
                "axis_title": (
                    current_axis.title
                    if current_axis
                    else ""
                ),
            },
        )

    def add_student_message(
        self,
        session: StudentSession,
        content: str,
        intent: str = "",
        mode: str = "",
        chapter: Chapter | None = None,
        axis: Axis | None = None,
        metadata: dict | None = None,
    ) -> StudentMessage:
        return self.add_message(
            session=session,
            role=StudentMessage.ROLE_STUDENT,
            content=content,
            intent=intent,
            mode=mode,
            chapter=chapter,
            axis=axis,
            metadata=metadata,
        )

    def add_assistant_message(
        self,
        session: StudentSession,
        content: str,
        intent: str = "",
        mode: str = "",
        chapter: Chapter | None = None,
        axis: Axis | None = None,
        metadata: dict | None = None,
    ) -> StudentMessage:
        return self.add_message(
            session=session,
            role=StudentMessage.ROLE_ASSISTANT,
            content=content,
            intent=intent,
            mode=mode,
            chapter=chapter,
            axis=axis,
            metadata=metadata,
        )

    def add_system_message(
        self,
        session: StudentSession,
        content: str,
        intent: str = "",
        mode: str = "",
        chapter: Chapter | None = None,
        axis: Axis | None = None,
        metadata: dict | None = None,
    ) -> StudentMessage:
        return self.add_message(
            session=session,
            role=StudentMessage.ROLE_SYSTEM,
            content=content,
            intent=intent,
            mode=mode,
            chapter=chapter,
            axis=axis,
            metadata=metadata,
        )

    def add_message(
        self,
        session: StudentSession,
        role: str,
        content: str,
        intent: str = "",
        mode: str = "",
        chapter: Chapter | None = None,
        axis: Axis | None = None,
        metadata: dict | None = None,
    ) -> StudentMessage:
        clean_content = (content or "").strip()

        if not clean_content:
            raise ValueError(
                "Le contenu du message ne peut pas être vide."
            )

        selected_chapter = chapter or session.chapter
        selected_axis = axis or session.current_axis

        if selected_axis and selected_chapter:
            self.validate_axis_chapter(
                axis=selected_axis,
                chapter=selected_chapter,
            )

        return StudentMessage.objects.create(
            session=session,
            role=role,
            content=clean_content,
            intent=intent or "",
            mode=mode or "",
            chapter=selected_chapter,
            axis=selected_axis,
            metadata=metadata or {},
        )

    @transaction.atomic
    def update_session_state(
        self,
        session: StudentSession,
        last_question: str = "",
        last_answer: str = "",
        current_intent: str = "",
        current_skill: str = "",
        chapter: Chapter | None = None,
        current_axis: Axis | None = None,
        metadata: dict | None = None,
    ) -> StudentSession:
        """
        Met à jour l'état courant de la session.

        On utilise désormais :
        - chapter au lieu de current_chapter ;
        - current_axis au lieu de current_axis_tag.
        """

        fields_to_update = []

        if last_question:
            session.last_question = last_question.strip()
            fields_to_update.append("last_question")

        if last_answer:
            session.last_answer = last_answer.strip()
            fields_to_update.append("last_answer")

        if current_intent:
            session.current_intent = current_intent
            fields_to_update.append("current_intent")

        if current_skill:
            session.current_skill = current_skill
            fields_to_update.append("current_skill")

        if chapter is not None:
            session.chapter = chapter
            fields_to_update.append("chapter")

        selected_chapter = chapter or session.chapter

        if current_axis is not None:
            if selected_chapter is None:
                raise ValueError(
                    "Impossible d'associer un axe sans chapitre."
                )

            self.validate_axis_chapter(
                axis=current_axis,
                chapter=selected_chapter,
            )

            session.current_axis = current_axis
            fields_to_update.append("current_axis")

        if metadata is not None:
            session.metadata = {
                **(session.metadata or {}),
                **metadata,
            }
            fields_to_update.append("metadata")

        if fields_to_update:
            fields_to_update.append("updated_at")

            session.save(
                update_fields=list(dict.fromkeys(fields_to_update)),
            )

        return session

    def get_context(
        self,
        session: StudentSession,
        limit: int = 10,
    ) -> SessionContext:
        history = list(
            session.messages
            .select_related(
                "chapter",
                "axis",
            )
            .order_by("-created_at", "-id")[:limit]
        )

        history.reverse()

        chapter = session.chapter
        current_axis = session.current_axis

        return SessionContext(
            session=session,
            history=history,

            last_question=session.last_question or "",
            last_answer=session.last_answer or "",

            current_skill=session.current_skill or "",
            current_intent=session.current_intent or "",

            chapter=chapter,
            current_axis=current_axis,

            chapter_id=chapter.id if chapter else None,
            chapter_code=chapter.code if chapter else "",
            chapter_title=chapter.title if chapter else "",

            axis_id=current_axis.id if current_axis else None,
            axis_tag=current_axis.tag if current_axis else "",
            axis_title=current_axis.title if current_axis else "",

            metadata=session.metadata or {},
        )

    def build_history_text(
            self,
            session: StudentSession,
            limit: int = 10,
    ) -> str:
        context = self.get_context(
            session=session,
            limit=limit,
        )

        if not context.history:
            return ""

        lines = []

        if context.chapter_title:
            lines.append(
                f"الفصل الحالي: {context.chapter_title}"
            )

        if context.axis_title:
            lines.append(
                f"المحور الحالي: {context.axis_title}"
            )

        lines.append("")

        for message in context.history:
            content = (
                    message.content or ""
            ).strip()

            if not content:
                continue

            if message.role == StudentMessage.ROLE_STUDENT:
                lines.append(
                    f"الطالب: {content}"
                )

            elif message.role == StudentMessage.ROLE_ASSISTANT:
                lines.append(
                    f"الأستاذ: {content}"
                )

            elif message.role == StudentMessage.ROLE_SYSTEM:
                lines.append(
                    f"النظام: {content}"
                )

        return "\n\n".join(lines).strip()
    @staticmethod
    def validate_axis_chapter(
        axis: Axis | None,
        chapter: Chapter | None,
    ) -> None:
        if axis is None:
            return

        if chapter is None:
            raise ValueError(
                "L'axe doit être associé à un chapitre."
            )

        if axis.chapter_id != chapter.id:
            raise ValueError(
                "L'axe sélectionné n'appartient pas au chapitre."
            )

    @transaction.atomic
    def update_session_axis(
            self,
            session: StudentSession,
            chapter: Chapter,
            current_axis: Axis | None,
    ) -> StudentSession:
        """
        Met à jour uniquement le chapitre et l'axe courant
        sans modifier last_question ou last_answer.
        """

        if current_axis is not None:
            self.validate_axis_chapter(
                axis=current_axis,
                chapter=chapter,
            )

        fields_to_update = []

        if session.chapter_id != chapter.id:
            session.chapter = chapter
            fields_to_update.append("chapter")

        if (
                current_axis is not None
                and session.current_axis_id != current_axis.id
        ):
            session.current_axis = current_axis
            fields_to_update.append("current_axis")

        metadata = {
            **(session.metadata or {}),
            "chapter_id": chapter.id,
            "chapter_code": chapter.code or "",
            "chapter_title": chapter.title or "",
            "axis_id": (
                current_axis.id
                if current_axis
                else session.current_axis_id
            ),
            "axis_tag": (
                current_axis.tag
                if current_axis
                else (
                    session.current_axis.tag
                    if session.current_axis
                    else ""
                )
            ),
            "axis_title": (
                current_axis.title
                if current_axis
                else (
                    session.current_axis.title
                    if session.current_axis
                    else ""
                )
            ),
        }

        session.metadata = metadata
        fields_to_update.append("metadata")

        fields_to_update.append("updated_at")

        session.save(
            update_fields=list(
                dict.fromkeys(fields_to_update)
            ),
        )

        return session