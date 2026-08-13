# tutor/services/context/context_builder.py

from tutor.models import RagChunk


class ContextBuilder:
    """
    Transforme les résultats RAG en contexte propre
    pour le LLM.
    """

    def build(
        self,
        *,
        chunks: list[RagChunk],
        max_chars: int = 6000,
    ) -> str:

        if not chunks:
            return ""

        parts = []
        total_length = 0
        seen_contents = set()

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            content = (chunk.content or "").strip()

            if not content:
                continue

            # منع التكرار
            normalized = " ".join(
                content.lower().split()
            )

            if normalized in seen_contents:
                continue

            seen_contents.add(normalized)

            source = self._format_chunk(
                chunk=chunk,
                index=index,
            )

            if total_length + len(source) > max_chars:
                break

            parts.append(source)
            total_length += len(source)

        return "\n\n".join(parts)

    def _format_chunk(
        self,
        *,
        chunk: RagChunk,
        index: int,
    ) -> str:

        axis_title = (
            chunk.axis.title
            if chunk.axis
            else ""
        )

        chapter_title = (
            chunk.chapter.title
            if chunk.chapter
            else ""
        )

        lines = [
            f"[SOURCE {index}]",
        ]

        if chapter_title:
            lines.append(
                f"الفصل: {chapter_title}"
            )

        if axis_title:
            lines.append(
                f"المحور: {axis_title}"
            )

        if chunk.title:
            lines.append(
                f"العنوان: {chunk.title}"
            )

        if chunk.year:
            lines.append(
                f"السنة: {chunk.year}"
            )

        lines.append(
            f"المحتوى:\n{chunk.content.strip()}"
        )

        return "\n".join(lines)