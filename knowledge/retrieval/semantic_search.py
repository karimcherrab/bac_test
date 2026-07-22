import math
from dataclasses import dataclass
from typing import Iterable

from sentence_transformers import SentenceTransformer

from course.models import Axis


@dataclass
class SearchResult:
    item: Axis
    score: float


class SemanticSearch:
    """
    Semantic search باستعمال BGE-M3 محليًا.
    يعمل مع:
    - Chapter
    - Axis
    - KnowledgeItem
    - KnowledgeEmbedding
    """

    _model = None

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name

        if SemanticSearch._model is None:
            SemanticSearch._model = SentenceTransformer(model_name)

        self.model = SemanticSearch._model

    def search(
        self,
        query: str,
        item_types: list[str] | None = None,
        chapter_code: str | None = None,
        axis_tag: str | None = None,
        candidate_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:

        query_vector = self.embed_query(query)

        qs = Axis.objects.select_related(
            "item",
            "item__axis",
            "item__axis__chapter",
        )

        if item_types:
            qs = qs.filter(item__item_type__in=item_types)

        if chapter_code:
            qs = qs.filter(item__chapter=chapter_code)

        if axis_tag:
            qs = qs.filter(item__axis__tag=axis_tag)

        if candidate_ids:
            qs = qs.filter(item_id__in=candidate_ids)

        results: list[SearchResult] = []

        for emb in qs.iterator():
            if not emb.vector:
                continue

            score = self.cosine_similarity(query_vector, emb.vector)

            results.append(
                SearchResult(
                    item=emb.item,
                    score=score,
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

    def search_lessons_by_axis(
        self,
        query: str,
        axis_tag: str,
        chapter_code: str = "sequences",
        top_k: int = 3,
    ) -> list[SearchResult]:

        return self.search(
            query=query,
            item_types=["lesson"],
            chapter_code=chapter_code,
            axis_tag=axis_tag,
            top_k=top_k,
        )

    def search_questions_by_axis(
        self,
        query: str,
        axis_tag: str,
        chapter_code: str = "sequences",
        top_k: int = 10,
    ) -> list[SearchResult]:

        return self.search(
            query=query,
            item_types=["bac_question"],
            chapter_code=chapter_code,
            axis_tag=axis_tag,
            top_k=top_k,
        )

    def search_axis_content(
        self,
        query: str,
        axis: Axis,
        item_types: list[str] | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:

        return self.search(
            query=query,
            item_types=item_types,
            chapter_code=axis.chapter.code,
            axis_tag=axis.tag,
            top_k=top_k,
        )

    def search_from_items(
        self,
        query: str,
        items: Iterable[Axis],
        top_k: int = 10,
    ) -> list[SearchResult]:

        item_ids = [item.id for item in items]

        if not item_ids:
            return []

        return self.search(
            query=query,
            candidate_ids=item_ids,
            top_k=top_k,
        )

    def embed_query(self, query: str) -> list[float]:
        vector = self.model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return vector.tolist()

    def cosine_similarity(
        self,
        vec1: list[float],
        vec2: list[float],
    ) -> float:

        if not vec1 or not vec2:
            return 0.0

        if len(vec1) != len(vec2):
            return 0.0

        dot = 0.0
        norm1 = 0.0
        norm2 = 0.0

        for a, b in zip(vec1, vec2):
            dot += a * b
            norm1 += a * a
            norm2 += b * b

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (math.sqrt(norm1) * math.sqrt(norm2))