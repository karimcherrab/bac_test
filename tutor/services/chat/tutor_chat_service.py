# tutor/services/chat/tutor_chat_service.py

from django.db import transaction

from tutor.models import (
    TutorChatMessage,
)

from tutor.services.retrieval.semantic_retriever import (
    SemanticRetriever,
)

from tutor.services.context.context_builder import (
    ContextBuilder,
)

from tutor.services.llm.groq_answer_service import (
    GroqAnswerService,
)


class TutorChatService:

    HISTORY_LIMIT = 8

    # سنعدله لاحقًا حسب الاختبارات
    MIN_RAG_SCORE = 0.45

    def __init__(self):
        self.retriever = (
            SemanticRetriever()
        )

        self.context_builder = (
            ContextBuilder()
        )

        self.llm = (
            GroqAnswerService()
        )

    def answer(
        self,
        *,
        student,
        question: str,
        session,
    ) -> dict:

        question = (
            question or ""
        ).strip()

        if not question:
            raise ValueError(
                "Question vide."
            )

        # ======================================
        # History
        # ======================================

        history = self._get_history(
            session=session
        )

        # ======================================
        # Retrieval
        # ======================================

        chunks = (
            self.retriever.search(
                query=question,

                chapter_id=(
                    session.chapter_id
                ),

                axis_id=(
                    session.axis_id
                ),

                source_type="lesson",

                limit=5,
            )
        )

        # ======================================
        # Decide RAG or GENERAL
        # ======================================

        best_score = 0.0

        if chunks:
            best_score = float(
                getattr(
                    chunks[0],
                    "final_score",
                    0.0,
                )
            )

        rag_is_relevant = (
            bool(chunks)
            and best_score
            >= self.MIN_RAG_SCORE
        )

        if rag_is_relevant:

            mode = "rag"

            context = (
                self
                .context_builder
                .build(
                    chunks=chunks[:4]
                )
            )

            used_chunks = chunks[:4]

        else:

            mode = "general"

            context = ""

            used_chunks = []

        # ======================================
        # Generate structured answer
        # ======================================

        answer_payload = (
            self.llm.generate(
                question=question,
                context=context,
                history=history,
                mode=mode,
            )
        )

        # ======================================
        # Create readable text for history
        # ======================================

        history_text = (
            self._answer_to_text(
                answer_payload
            )
        )

        # ======================================
        # Sources
        # ======================================

        sources = []

        for chunk in used_chunks:

            sources.append(
                {
                    "rag_chunk_id":
                        chunk.id,

                    "source_type":
                        chunk.source_type,

                    "source_id":
                        chunk.source_id,

                    "title":
                        chunk.title,

                    "chapter_id":
                        chunk.chapter_id,

                    "axis_id":
                        chunk.axis_id,

                    "score":
                        round(
                            float(
                                chunk
                                .final_score
                            ),
                            4,
                        ),
                }
            )

        # ======================================
        # Save
        # ======================================

        with transaction.atomic():

            TutorChatMessage.objects.create(
                session=session,
                role="user",
                content=question,
            )

            assistant_message = (
                TutorChatMessage
                .objects
                .create(
                    session=session,

                    role="assistant",

                    content=history_text,

                    sources=sources,

                    metadata={
                        "answer_payload":
                            answer_payload,

                        "answer_mode":
                            mode,
                    },
                )
            )

            if not session.title:

                session.title = (
                    question[:80]
                )

            session.save(
                update_fields=[
                    "title",
                    "updated_at",
                ]
            )

        return {
            "session_id":
                str(session.id),

            "message_id":
                assistant_message.id,

            # JSON منظم للـReact
            "answer":
                answer_payload,

            "mode":
                mode,

            "sources":
                sources,
        }

    def _get_history(
        self,
        *,
        session,
    ) -> list[dict]:

        messages = list(
            session.messages
            .order_by(
                "-created_at",
                "-id",
            )
            .values(
                "role",
                "content",
            )[
                :self.HISTORY_LIMIT
            ]
        )

        messages.reverse()

        return messages

    def _answer_to_text(
        self,
        answer: dict,
    ) -> str:

        parts = []

        title = answer.get(
            "title"
        )

        if title:
            parts.append(title)

        intro = answer.get(
            "intro"
        )

        if intro:
            parts.append(intro)

        for block in answer.get(
            "blocks",
            [],
        ):

            if not isinstance(
                block,
                dict,
            ):
                continue

            block_type = block.get(
                "type"
            )

            if block_type == "text":

                content = block.get(
                    "content"
                )

                if content:
                    parts.append(
                        str(content)
                    )

            elif block_type == "math":

                latex = block.get(
                    "latex"
                )

                if latex:
                    parts.append(
                        str(latex)
                    )

            elif block_type == "steps":

                items = block.get(
                    "items",
                    [],
                )

                if isinstance(
                    items,
                    list,
                ):
                    parts.extend(
                        str(item)
                        for item in items
                        if item
                    )

        summary = answer.get(
            "summary"
        )

        if summary:
            parts.append(summary)

        return "\n".join(parts)