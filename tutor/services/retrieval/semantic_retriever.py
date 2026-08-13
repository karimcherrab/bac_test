import re

from pgvector.django import CosineDistance

from tutor.models import RagChunk
from tutor.services.embeddings.embedding_service import (
    EmbeddingService,
)


class SemanticRetriever:

    def search(
        self,
        *,
        query: str,
        chapter_id: int | None = None,
        axis_id: int | None = None,
        source_type: str | None = None,
        limit: int = 5,
    ):
        query = (query or "").strip()

        if not query:
            return []

        query_embedding = EmbeddingService.encode(query)

        queryset = RagChunk.objects.filter(
            is_active=True,
            embedding__isnull=False,
        )

        if chapter_id is not None:
            queryset = queryset.filter(
                chapter_id=chapter_id
            )

        if axis_id is not None:
            queryset = queryset.filter(
                axis_id=axis_id
            )

        if source_type:
            queryset = queryset.filter(
                source_type=source_type
            )

        # نأخذ عددًا أكبر semantic ثم نعيد ترتيبهم
        candidates = list(
            queryset
            .annotate(
                distance=CosineDistance(
                    "embedding",
                    query_embedding,
                )
            )
            .order_by("distance")[:20]
        )

        query_words = self._extract_words(query)

        for chunk in candidates:
            keyword_score = self._keyword_score(
                query_words=query_words,
                chunk=chunk,
            )

            # كلما distance أصغر كان أفضل
            semantic_score = 1.0 - float(
                chunk.distance
            )

            chunk.semantic_score = semantic_score
            chunk.keyword_score = keyword_score

            # Hybrid score
            chunk.final_score = (
                semantic_score * 0.75
                +
                keyword_score * 0.25
            )

        candidates.sort(
            key=lambda item: item.final_score,
            reverse=True,
        )

        return candidates[:limit]

    def _keyword_score(
        self,
        *,
        query_words: set[str],
        chunk: RagChunk,
    ) -> float:

        if not query_words:
            return 0.0

        title_words = self._extract_words(
            chunk.title or ""
        )

        content_words = self._extract_words(
            chunk.content or ""
        )

        # العنوان أهم من المحتوى
        title_matches = len(
            query_words & title_words
        )

        content_matches = len(
            query_words & content_words
        )

        title_score = (
            title_matches
            / len(query_words)
        )

        content_score = (
            content_matches
            / len(query_words)
        )

        score = (
            title_score * 0.7
            +
            content_score * 0.3
        )

        return min(score, 1.0)

    @staticmethod
    def _extract_words(
        text: str,
    ) -> set[str]:

        text = text.lower()

        words = re.findall(
            r"[\u0600-\u06FFa-zA-Z0-9]+",
            text,
        )

        stop_words = {
            "كيف",
            "ما",
            "ماذا",
            "من",
            "في",
            "على",
            "إلى",
            "الى",
            "هل",
            "هو",
            "هي",
            "عن",
            "أعرف",
            "اعرف",
        }

        return {
            word
            for word in words
            if len(word) > 1
            and word not in stop_words
        }