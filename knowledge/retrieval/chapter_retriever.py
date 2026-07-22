# knowledge/retrieval/chapter_retriever.py

import json
from dataclasses import dataclass, field
from typing import Any

from django.db.models import QuerySet

from course.models import Axis, Chapter


@dataclass
class AxisScore:
    axis: Axis
    score: int


@dataclass
class ChapterRetrieveResult:
    chapter: Chapter
    selected_axis: Axis | None
    axes: list[Axis] = field(default_factory=list)
    exercises: list[Any] = field(default_factory=list)


class ChapterRetriever:
    AXIS_KEYWORDS = {
        "seq_recursive": [
            "تراجعية",
            "u_{n+1}",
            "un+1",
            "f(u_n)",
            "سلم",
            "تمثيل بياني",
        ],
        "seq_geometric": [
            "هندسية",
            "أساس هندسية",
            "q",
            "geometrique",
            "géométrique",
        ],
        "seq_arithmetic": [
            "حسابية",
            "أساس حسابية",
            "r",
            "arithmetique",
            "arithmétique",
        ],
        "seq_monotonicity": [
            "رتابة",
            "متزايدة",
            "متناقصة",
            "اتجاه التغير",
            "u_{n+1}-u_n",
        ],
        "seq_limits": [
            "نهاية",
            "تقارب",
            "متقاربة",
            "lim",
            "تؤول",
        ],
        "seq_induction": [
            "بالتراجع",
            "الاستدلال بالتراجع",
            "فرضية التراجع",
            "récurrence",
        ],
        "seq_bounded": [
            "محدودة",
            "محصورة",
            "حصر",
            "أكبر من",
            "أصغر من",
        ],
        "seq_adjacent": [
            "متجاورتان",
            "متتاليتان متجاورتان",
            "adjacentes",
        ],
        "seq_sum": [
            "مجموع",
            "مجموع الحدود",
            "somme",
        ],
    }

    def retrieve(
        self,
        chapter_id: int,
        question: str,
        exercises_limit: int = 3,
    ) -> ChapterRetrieveResult:

        chapter = Chapter.objects.get(
            id=chapter_id,
            is_active=True,
        )

        axes = list(
            Axis.objects.filter(
                chapter=chapter,
                is_active=True,
            )
            .select_related("chapter")
            .order_by("order", "id")
        )

        selected_axis = self.select_best_axis(
            question=question,
            axes=axes,
        )

        exercises = self.get_exercises(
            chapter=chapter,
            selected_axis=selected_axis,
            limit=exercises_limit,
        )

        return ChapterRetrieveResult(
            chapter=chapter,
            selected_axis=selected_axis,
            axes=axes,
            exercises=exercises,
        )

    def select_best_axis(
        self,
        question: str,
        axes: list[Axis],
    ) -> Axis | None:

        if not axes:
            return None

        normalized_question = question.lower().strip()
        scored_axes: list[AxisScore] = []

        for axis in axes:
            score = 0

            title = (axis.title or "").lower()
            tag = (axis.tag or "").lower()
            content_text = self.content_to_text(axis.content).lower()

            if title and title in normalized_question:
                score += 10

            keywords = self.AXIS_KEYWORDS.get(tag, [])

            for keyword in keywords:
                if keyword.lower() in normalized_question:
                    score += 5

            question_words = {
                word
                for word in normalized_question.split()
                if len(word) >= 3
            }

            for word in question_words:
                if word in title:
                    score += 2
                elif word in content_text:
                    score += 1

            scored_axes.append(
                AxisScore(
                    axis=axis,
                    score=score,
                )
            )

        scored_axes.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        best = scored_axes[0]

        if best.score <= 0:
            return None

        return best.axis

    def get_exercises(
        self,
        chapter: Chapter,
        selected_axis: Axis | None,
        limit: int,
    ) -> list[Any]:
        """
        Adapte uniquement cette méthode au nom réel
        de ton modèle ExerciseBac.
        """

        try:
            from bac.models import ExerciseBac
        except ImportError:
            return []

        queryset: QuerySet = ExerciseBac.objects.filter(
            chapter=chapter,
        ).order_by("-year", "exercise_number")

        if selected_axis:
            # axis_tags est un JSONField contenant une liste de tags.
            queryset = queryset.filter(
                axis_tags__contains=[selected_axis.tag],
            )

        return list(queryset[:limit])

    @staticmethod
    def content_to_text(content: Any) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        try:
            return json.dumps(
                content,
                ensure_ascii=False,
            )
        except (TypeError, ValueError):
            return str(content)