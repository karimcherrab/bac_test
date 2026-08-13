from typing import Any

from course.models import Axis
from tutor.models import RagChunk
from tutor.services.embeddings.embedding_service import (
    EmbeddingService,
)

class LessonIngestor:
    """
    تحويل محتوى Axis.content إلى RagChunk.
    """

    SOURCE_TYPE = "lesson"

    def ingest_axis(self, axis: Axis) -> int:
        """
        يحذف الـ chunks القديمة الخاصة بهذا المحور
        ثم يعيد بناءها.

        يرجع عدد الـ chunks التي تم إنشاؤها.
        """

        if not isinstance(axis.content, dict):
            return 0

        RagChunk.objects.filter(
            source_type=self.SOURCE_TYPE,
            source_id=axis.id,
        ).delete()

        chunks = self._build_chunks(axis)

        if not chunks:
            return 0

        RagChunk.objects.bulk_create(chunks)

        return len(chunks)

    def ingest_all(self) -> int:
        """
        إدخال جميع المحاور النشطة.
        """

        total = 0

        axes = (
            Axis.objects
            .filter(is_active=True)
            .select_related(
                "chapter",
                "chapter__subject",
            )
            .order_by(
                "chapter_id",
                "order",
                "id",
            )
        )

        for axis in axes:
            total += self.ingest_axis(axis)

        return total

    def _build_chunks(
        self,
        axis: Axis,
    ) -> list[RagChunk]:

        content = axis.content

        chunks: list[RagChunk] = []

        # --------------------------------------------------
        # 1. مقدمة / الهدف من الدرس
        # --------------------------------------------------

        lesson_goal = self._text(
            content.get("lesson_goal")
        )

        if lesson_goal:
            chunks.append(
                self._make_chunk(
                    axis=axis,
                    chunk_key=f"axis_{axis.id}_goal",
                    title=f"{axis.title} - هدف الدرس",
                    text=lesson_goal,
                    metadata={
                        "section": "lesson_goal",
                        "axis_tag": axis.tag,
                    },
                )
            )

        # --------------------------------------------------
        # 2. الفكرة الرئيسية / استراتيجية الدرس
        # --------------------------------------------------

        strategy = content.get(
            "lesson_strategy",
            {},
        )

        if isinstance(strategy, dict):

            strategy_texts = []

            main_idea = self._text(
                strategy.get("main_idea")
            )

            bac_skill = self._text(
                strategy.get("bac_skill")
            )

            common_obstacle = self._text(
                strategy.get("common_obstacle")
            )

            if main_idea:
                strategy_texts.append(
                    f"الفكرة الأساسية: {main_idea}"
                )

            if bac_skill:
                strategy_texts.append(
                    f"مهارة البكالوريا: {bac_skill}"
                )

            if common_obstacle:
                strategy_texts.append(
                    f"الصعوبة الشائعة: {common_obstacle}"
                )

            if strategy_texts:
                chunks.append(
                    self._make_chunk(
                        axis=axis,
                        chunk_key=(
                            f"axis_{axis.id}_strategy"
                        ),
                        title=(
                            f"{axis.title} - "
                            "الفكرة الأساسية"
                        ),
                        text="\n".join(
                            strategy_texts
                        ),
                        metadata={
                            "section":
                                "lesson_strategy",
                            "axis_tag":
                                axis.tag,
                        },
                    )
                )

        # --------------------------------------------------
        # 3. خطوات الشرح
        # --------------------------------------------------

        learning_path = content.get(
            "learning_path",
            [],
        )

        if isinstance(learning_path, list):

            for index, step in enumerate(
                learning_path,
                start=1,
            ):

                if not isinstance(step, dict):
                    continue

                chunk = self._build_step_chunk(
                    axis=axis,
                    step=step,
                    index=index,
                )

                if chunk:
                    chunks.append(chunk)

        # --------------------------------------------------
        # 4. ملخص الدرس
        # --------------------------------------------------

        summary = content.get(
            "lesson_summary",
            {},
        )

        if isinstance(summary, dict):

            summary_text = self._build_summary_text(
                summary
            )

            if summary_text:
                chunks.append(
                    self._make_chunk(
                        axis=axis,
                        chunk_key=(
                            f"axis_{axis.id}_summary"
                        ),
                        title=(
                            f"{axis.title} - "
                            "ملخص الدرس"
                        ),
                        text=summary_text,
                        metadata={
                            "section":
                                "lesson_summary",
                            "axis_tag":
                                axis.tag,
                        },
                    )
                )

        return chunks

    def _build_step_chunk(
        self,
        *,
        axis: Axis,
        step: dict[str, Any],
        index: int,
    ) -> RagChunk | None:

        step_id = str(
            step.get("id")
            or index
        )

        step_type = self._text(
            step.get("type")
        )

        step_title = self._text(
            step.get("title")
        )

        step_content = step.get(
            "content",
            {},
        )

        texts = []

        if isinstance(step_content, dict):

            teacher = self._text(
                step_content.get("teacher")
            )

            central_idea = self._text(
                step_content.get("central_idea")
            )

            memory_tip = self._text(
                step_content.get("memory_tip")
            )

            if teacher:
                texts.append(teacher)

            if central_idea:
                texts.append(
                    f"الفكرة الأساسية: {central_idea}"
                )

            if memory_tip:
                texts.append(
                    f"تذكر: {memory_tip}"
                )

        elif isinstance(step_content, str):

            text = step_content.strip()

            if text:
                texts.append(text)

        if not texts:
            return None

        title = (
            step_title
            or f"{axis.title} - المرحلة {index}"
        )

        return self._make_chunk(
            axis=axis,
            chunk_key=(
                f"axis_{axis.id}_step_{step_id}"
            ),
            title=title,
            text="\n".join(texts),
            metadata={
                "section": "learning_path",
                "step_id": step_id,
                "step_type": step_type,
                "step_index": index,
                "axis_tag": axis.tag,
            },
        )

    def _build_summary_text(
        self,
        summary: dict[str, Any],
    ) -> str:

        parts = []

        key_ideas = summary.get(
            "key_ideas",
            [],
        )

        if isinstance(key_ideas, list):

            values = [
                self._text(item)
                for item in key_ideas
            ]

            values = [
                value
                for value in values
                if value
            ]

            if values:
                parts.append(
                    "الأفكار الأساسية:\n"
                    + "\n".join(
                        f"- {value}"
                        for value in values
                    )
                )

        method_template = summary.get(
            "method_template",
            [],
        )

        if isinstance(method_template, list):

            values = [
                self._text(item)
                for item in method_template
            ]

            values = [
                value
                for value in values
                if value
            ]

            if values:
                parts.append(
                    "المنهجية:\n"
                    + "\n".join(
                        f"- {value}"
                        for value in values
                    )
                )

        memory_tip = self._text(
            summary.get("memory_tip")
        )

        if memory_tip:
            parts.append(
                f"نصيحة للحفظ: {memory_tip}"
            )

        return "\n\n".join(parts)

    def _make_chunk(
        self,
        *,
        axis: Axis,
        chunk_key: str,
        title: str,
        text: str,
        metadata: dict[str, Any],
    ) -> RagChunk:
        embedding_text = f"{title}\n{text}".strip()

        return RagChunk(
            source_type=self.SOURCE_TYPE,
            source_id=axis.id,

            chunk_key=chunk_key,

            subject=axis.chapter.subject,
            chapter=axis.chapter,
            axis=axis,

            year=None,

            title=title,

            content=text.strip(),

            metadata=metadata,

            # embedding يبقى فارغًا الآن
            # embedding=EmbeddingService.encode(
            #     text
            # ),

            embedding = EmbeddingService.encode(
                embedding_text
            ),

            is_active=True,
        )

    @staticmethod
    def _text(
        value: Any,
    ) -> str:

        if isinstance(value, str):
            return value.strip()

        return ""