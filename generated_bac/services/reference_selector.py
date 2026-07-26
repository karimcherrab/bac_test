import random
from collections import defaultdict
from typing import Any

from exercise_bac.models import ExerciseBac

from .exceptions import NoReferenceExercisesError


class BacReferenceSelector:
    """
    اختيار تمارين بكالوريا حقيقية وفق شرطين فقط:

    1. chapter_id
    2. branch_code

    الاستراتيجيات:
    - diverse_random:
      اختيار عشوائي مع محاولة تنويع السنوات.
    - random:
      اختيار عشوائي مباشر من مجموعة محدودة.
    - latest_random:
      الاختيار عشوائيًا من أحدث التمارين.
    """

    MAX_POOL_SIZE = 80

    def select(
        self,
        *,
        chapter_id: int,
        branch_code: str,
        limit: int = 2,
        strategy: str = "diverse_random",
    ) -> list[ExerciseBac]:
        queryset = (
            ExerciseBac.objects
            .filter(
                chapter_id=chapter_id,
                branches__code=branch_code,
                is_active=True,
            )
            .prefetch_related("branches")
            .distinct()
        )

        if not queryset.exists():
            raise NoReferenceExercisesError(
                "لا توجد تمارين بكالوريا مطابقة "
                "لهذه الوحدة وهذه الشعبة."
            )

        if queryset.count() < 2:
            raise NoReferenceExercisesError(
                "يجب توفير تمرينين حقيقيين على الأقل "
                "لنفس الوحدة والشعبة."
            )

        if strategy == "latest_random":
            pool = list(
                queryset.order_by(
                    "-year",
                    "exercise_number",
                )[: self.MAX_POOL_SIZE]
            )
            random.shuffle(pool)
            return pool[: min(limit, len(pool))]

        pool = list(
            queryset.order_by(
                "-year",
                "exercise_number",
            )[: self.MAX_POOL_SIZE]
        )

        if strategy == "random":
            random.shuffle(pool)
            return pool[: min(limit, len(pool))]

        return self._select_diverse_years(
            pool=pool,
            limit=limit,
        )

    def compact_for_exercise_generation(
        self,
        exercises: list[ExerciseBac],
    ) -> list[dict[str, Any]]:
        """
        نرسل إلى AI:
        - نص التمرين.
        - أقسام المعطيات.
        - نصوص الأسئلة.
        - المحاور.
        - المهارة والاستراتيجية المختصرة إن وُجدت.

        لا نرسل:
        - graph_data الضخم.
        - خطوات الحل الطويلة.
        - الجداول البيانية الثقيلة.
        """

        return [
            self._compact_exercise(exercise)
            for exercise in exercises
        ]

    def compact_for_solution_style(
        self,
        exercise_ids: list[int],
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        exercises = list(
            ExerciseBac.objects
            .filter(
                id__in=exercise_ids,
                is_active=True,
            )
            .order_by("-year")[:limit]
        )

        return [
            self._compact_solution(exercise)
            for exercise in exercises
        ]

    def _select_diverse_years(
        self,
        *,
        pool: list[ExerciseBac],
        limit: int,
    ) -> list[ExerciseBac]:
        by_year: dict[int, list[ExerciseBac]] = defaultdict(list)

        for exercise in pool:
            by_year[exercise.year].append(exercise)

        years = list(by_year.keys())
        random.shuffle(years)

        selected: list[ExerciseBac] = []

        # أولًا نحاول أخذ تمرين واحد من كل سنة مختلفة.
        for year in years:
            if len(selected) >= limit:
                break

            selected.append(
                random.choice(by_year[year])
            )

        # إذا لم نصل للعدد المطلوب، نكمل عشوائيًا.
        if len(selected) < limit:
            selected_ids = {
                exercise.id
                for exercise in selected
            }

            remaining = [
                exercise
                for exercise in pool
                if exercise.id not in selected_ids
            ]

            random.shuffle(remaining)

            selected.extend(
                remaining[: limit - len(selected)]
            )

        return selected[:limit]

    def _compact_exercise(
        self,
        exercise: ExerciseBac,
    ) -> dict[str, Any]:
        content = (
            exercise.content
            if isinstance(exercise.content, dict)
            else {}
        )

        compact_questions = []

        for question in content.get(
            "questions",
            [],
        )[:8]:
            if not isinstance(question, dict):
                continue

            solution = question.get(
                "solution",
                {},
            )

            methodology = (
                solution.get("methodology", {})
                if isinstance(solution, dict)
                else {}
            )

            compact_questions.append(
                {
                    "text": self._truncate(
                        question.get("text", ""),
                        750,
                    ),
                    "axis_tags": question.get(
                        "axis_tags",
                        [],
                    ),
                    "method_goal": methodology.get(
                        "goal",
                        "",
                    ),
                    "method": methodology.get(
                        "method",
                        "",
                    ),
                }
            )

        sections = []

        for section in content.get(
            "statement_sections",
            [],
        )[:6]:
            if not isinstance(section, dict):
                continue

            sections.append(
                {
                    "type": section.get(
                        "type",
                        "",
                    ),
                    "text": self._truncate(
                        section.get("text", ""),
                        600,
                    ),
                }
            )

        return {
            "database_id": exercise.id,
            "code": exercise.code,
            "year": exercise.year,
            "exercise_number": exercise.exercise_number,
            "title": exercise.title,
            "branch_codes": exercise.branch_codes,
            "chapter_id": exercise.chapter_id,
            "axis_tags": exercise.axis_tags,
            "statement": self._truncate(
                content.get("statement", ""),
                1500,
            ),
            "statement_sections": sections,
            "questions": compact_questions,
        }

    def _compact_solution(
        self,
        exercise: ExerciseBac,
    ) -> dict[str, Any]:
        content = (
            exercise.content
            if isinstance(exercise.content, dict)
            else {}
        )

        compact_questions = []

        for question in content.get(
            "questions",
            [],
        )[:5]:
            if not isinstance(question, dict):
                continue

            solution = question.get(
                "solution",
                {},
            )

            if not isinstance(solution, dict):
                continue

            steps = []

            for step in solution.get(
                "steps",
                [],
            )[:6]:
                if not isinstance(step, dict):
                    continue

                steps.append(
                    {
                        "title": step.get(
                            "title",
                            "",
                        ),
                        "explanation": self._truncate(
                            step.get(
                                "explanation",
                                "",
                            ),
                            350,
                        ),
                        "latex": self._truncate(
                            step.get(
                                "latex",
                                "",
                            ),
                            280,
                        ),
                    }
                )

            compact_questions.append(
                {
                    "question": self._truncate(
                        question.get("text", ""),
                        500,
                    ),
                    "strategy": self._truncate(
                        solution.get(
                            "strategy",
                            "",
                        ),
                        350,
                    ),
                    "steps": steps,
                    "final_answer": self._truncate(
                        solution.get(
                            "final_answer",
                            "",
                        ),
                        350,
                    ),
                }
            )

        return {
            "code": exercise.code,
            "year": exercise.year,
            "questions": compact_questions,
        }

    @staticmethod
    def _truncate(
        value: Any,
        max_chars: int,
    ) -> str:
        text = str(value or "").strip()

        if len(text) <= max_chars:
            return text

        return text[:max_chars].rstrip() + "…"
