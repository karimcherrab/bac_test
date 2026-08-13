# tutor/services/ingestion/bac_exercise_ingestor.py

from typing import Any

from exercise_bac.models import ExerciseBac
from tutor.models import RagChunk

from tutor.services.embeddings.embedding_service import (
    EmbeddingService,
)


class BacExerciseIngestor:
    """
    تحويل ExerciseBac إلى RagChunks قابلة للبحث الدلالي.

    البيانات الأصلية تبقى في ExerciseBac.
    RagChunk مجرد index للـAI.
    """

    SOURCE_TYPE = "bac_exercise"

    # -----------------------------------------------------
    # Public methods
    # -----------------------------------------------------

    def ingest_exercise(
        self,
        exercise: ExerciseBac,
    ) -> int:
        """
        إعادة بناء جميع chunks الخاصة بتمرين واحد.
        """

        if not isinstance(
            exercise.content,
            dict,
        ):
            return 0

        # حذف النسخة القديمة من الفهرس فقط.
        # لا نحذف ExerciseBac.
        RagChunk.objects.filter(
            source_type=self.SOURCE_TYPE,
            source_id=exercise.id,
        ).delete()

        chunks = self._build_chunks(
            exercise
        )

        if not chunks:
            return 0

        RagChunk.objects.bulk_create(
            chunks
        )

        return len(chunks)

    def ingest_all(self) -> int:
        """
        إدخال جميع تمارين البكالوريا النشطة.
        """

        total = 0

        exercises = (
            ExerciseBac.objects
            .filter(
                is_active=True,
            )
            .select_related(
                "chapter",
                "chapter__subject",
            )
            .prefetch_related(
                "branches",
            )
            .order_by(
                "year",
                "exercise_number",
                "id",
            )
        )

        for exercise in exercises:

            count = self.ingest_exercise(
                exercise
            )

            total += count

            print(
                f"[BAC] "
                f"{exercise.year} "
                f"- Ex {exercise.exercise_number} "
                f"- {count} chunks"
            )

        return total

    # -----------------------------------------------------
    # Build chunks
    # -----------------------------------------------------

    def _build_chunks(
        self,
        exercise: ExerciseBac,
    ) -> list[RagChunk]:

        chunks: list[RagChunk] = []

        content = exercise.content

        # =================================================
        # 1. Statement principal
        # =================================================

        statement = self._text(
            content.get(
                "statement"
            )
        )

        if statement:

            chunks.append(
                self._make_chunk(
                    exercise=exercise,

                    chunk_key=(
                        f"bac_{exercise.id}"
                        "_statement"
                    ),

                    title=(
                        f"Bac {exercise.year} - "
                        f"Exercice "
                        f"{exercise.exercise_number} - "
                        f"{exercise.title}"
                    ),

                    text=statement,

                    metadata={
                        "section":
                            "statement",
                    },
                )
            )

        # =================================================
        # 2. Statement sections
        # =================================================

        statement_sections = (
            content.get(
                "statement_sections",
                [],
            )
        )

        if isinstance(
            statement_sections,
            list,
        ):

            for index, section in enumerate(
                statement_sections,
                start=1,
            ):

                section_text = (
                    self._extract_text(
                        section
                    )
                )

                if not section_text:
                    continue

                section_title = (
                    self._get_title(
                        section
                    )
                    or (
                        f"جزء {index} "
                        f"من نص التمرين"
                    )
                )

                chunks.append(
                    self._make_chunk(
                        exercise=exercise,

                        chunk_key=(
                            f"bac_{exercise.id}"
                            f"_statement_section_{index}"
                        ),

                        title=(
                            f"Bac {exercise.year} - "
                            f"{section_title}"
                        ),

                        text=section_text,

                        metadata={
                            "section":
                                "statement_section",

                            "section_index":
                                index,
                        },
                    )
                )

        # =================================================
        # 3. Questions
        # =================================================

        questions = content.get(
            "questions",
            [],
        )

        if isinstance(
            questions,
            list,
        ):

            for index, question in enumerate(
                questions,
                start=1,
            ):

                if not isinstance(
                    question,
                    dict,
                ):
                    continue

                self._append_question_chunks(
                    chunks=chunks,
                    exercise=exercise,
                    question=question,
                    index=index,
                )

        # =================================================
        # 4. Solution globale éventuelle
        # =================================================

        global_solution = (
            content.get("solution")
            or content.get("correction")
            or content.get(
                "detailed_solution"
            )
        )

        solution_text = (
            self._extract_text(
                global_solution
            )
        )

        if solution_text:

            chunks.append(
                self._make_chunk(
                    exercise=exercise,

                    chunk_key=(
                        f"bac_{exercise.id}"
                        "_global_solution"
                    ),

                    title=(
                        f"حل Bac {exercise.year} - "
                        f"التمرين "
                        f"{exercise.exercise_number}"
                    ),

                    text=solution_text,

                    metadata={
                        "section":
                            "solution",

                        "solution_scope":
                            "exercise",
                    },
                )
            )

        return chunks

    # -----------------------------------------------------
    # Question
    # -----------------------------------------------------

    def _append_question_chunks(
        self,
        *,
        chunks: list[RagChunk],
        exercise: ExerciseBac,
        question: dict[str, Any],
        index: int,
    ) -> None:

        question_id = str(
            question.get("id")
            or question.get("code")
            or question.get("number")
            or index
        )

        question_number = str(
            question.get("number")
            or question.get(
                "question_number"
            )
            or question_id
        )

        question_title = (
            self._get_title(
                question
            )
            or (
                f"السؤال "
                f"{question_number}"
            )
        )

        # ---------------------------------------------
        # Texte de la question
        # ---------------------------------------------

        question_text = (
            self._extract_question_text(
                question
            )
        )

        if question_text:

            chunks.append(
                self._make_chunk(
                    exercise=exercise,

                    chunk_key=(
                        f"bac_{exercise.id}"
                        f"_question_{question_id}"
                    ),

                    title=(
                        f"Bac {exercise.year} - "
                        f"{question_title}"
                    ),

                    text=question_text,

                    metadata={
                        "section":
                            "question",

                        "question_id":
                            question_id,

                        "question_number":
                            question_number,

                        "question_index":
                            index,
                    },
                )
            )

        # ---------------------------------------------
        # Solution contenue dans la question
        # ---------------------------------------------

        solution = (
            question.get("solution")
            or question.get("answer")
            or question.get(
                "correction"
            )
            or question.get(
                "detailed_solution"
            )
        )

        solution_text = (
            self._extract_text(
                solution
            )
        )

        if solution_text:

            chunks.append(
                self._make_chunk(
                    exercise=exercise,

                    chunk_key=(
                        f"bac_{exercise.id}"
                        f"_solution_{question_id}"
                    ),

                    title=(
                        f"حل {question_title} - "
                        f"Bac {exercise.year}"
                    ),

                    text=solution_text,

                    metadata={
                        "section":
                            "solution",

                        "solution_scope":
                            "question",

                        "question_id":
                            question_id,

                        "question_number":
                            question_number,

                        "question_index":
                            index,
                    },
                )
            )

        # ---------------------------------------------
        # Sous-questions éventuelles
        # ---------------------------------------------

        subquestions = (
            question.get(
                "subquestions"
            )
            or question.get(
                "children"
            )
            or question.get(
                "questions"
            )
            or []
        )

        if not isinstance(
            subquestions,
            list,
        ):
            return

        for sub_index, subquestion in enumerate(
            subquestions,
            start=1,
        ):

            if not isinstance(
                subquestion,
                dict,
            ):
                continue

            sub_id = str(
                subquestion.get("id")
                or subquestion.get(
                    "number"
                )
                or (
                    f"{question_id}_"
                    f"{sub_index}"
                )
            )

            sub_number = str(
                subquestion.get(
                    "number"
                )
                or sub_id
            )

            sub_title = (
                self._get_title(
                    subquestion
                )
                or (
                    f"السؤال "
                    f"{sub_number}"
                )
            )

            sub_text = (
                self._extract_question_text(
                    subquestion
                )
            )

            if sub_text:

                chunks.append(
                    self._make_chunk(
                        exercise=exercise,

                        chunk_key=(
                            f"bac_{exercise.id}"
                            f"_question_{sub_id}"
                        ),

                        title=(
                            f"Bac "
                            f"{exercise.year} - "
                            f"{sub_title}"
                        ),

                        text=sub_text,

                        metadata={
                            "section":
                                "question",

                            "question_id":
                                sub_id,

                            "question_number":
                                sub_number,

                            "parent_question_id":
                                question_id,

                            "question_index":
                                index,

                            "subquestion_index":
                                sub_index,
                        },
                    )
                )

            sub_solution = (
                subquestion.get(
                    "solution"
                )
                or subquestion.get(
                    "answer"
                )
                or subquestion.get(
                    "correction"
                )
            )

            sub_solution_text = (
                self._extract_text(
                    sub_solution
                )
            )

            if sub_solution_text:

                chunks.append(
                    self._make_chunk(
                        exercise=exercise,

                        chunk_key=(
                            f"bac_{exercise.id}"
                            f"_solution_{sub_id}"
                        ),

                        title=(
                            f"حل {sub_title} - "
                            f"Bac "
                            f"{exercise.year}"
                        ),

                        text=(
                            sub_solution_text
                        ),

                        metadata={
                            "section":
                                "solution",

                            "solution_scope":
                                "question",

                            "question_id":
                                sub_id,

                            "question_number":
                                sub_number,

                            "parent_question_id":
                                question_id,
                        },
                    )
                )

    # -----------------------------------------------------
    # Make RagChunk
    # -----------------------------------------------------

    def _make_chunk(
        self,
        *,
        exercise: ExerciseBac,
        chunk_key: str,
        title: str,
        text: str,
        metadata: dict[str, Any],
    ) -> RagChunk:

        text = text.strip()

        branch_codes = list(
            exercise.branches.values_list(
                "code",
                flat=True,
            )
        )

        branch_names = list(
            exercise.branches.values_list(
                "name",
                flat=True,
            )
        )

        base_metadata = {
            # Source
            "exercise_id":
                exercise.id,

            "exercise_code":
                exercise.code,

            "exercise_number":
                exercise.exercise_number,

            "year":
                exercise.year,

            "source_page":
                exercise.source_page,

            "source_filename":
                exercise.source_filename,

            # Axes
            "axis_tags":
                (
                    exercise.axis_tags
                    if isinstance(
                        exercise.axis_tags,
                        list,
                    )
                    else []
                ),

            # Branches
            "branch_codes":
                branch_codes,

            "branch_names":
                branch_names,

            # Schema
            "schema_version":
                exercise.schema_version,

            "language":
                exercise.language,

            "direction":
                exercise.direction,

            **metadata,
        }

        # Important:
        # embedding = titre + texte
        embedding_text = (
            f"{title}\n{text}"
        ).strip()

        embedding = (
            EmbeddingService.encode(
                embedding_text
            )
        )

        return RagChunk(
            source_type=(
                self.SOURCE_TYPE
            ),

            source_id=(
                exercise.id
            ),

            chunk_key=(
                chunk_key
            ),

            subject=(
                exercise.chapter.subject
                if exercise.chapter
                else None
            ),

            chapter=(
                exercise.chapter
            ),

            # ExerciseBac possède axis_tags,
            # pas nécessairement un seul Axis.
            axis=None,

            year=(
                exercise.year
            ),

            title=(
                title
            ),

            content=(
                text
            ),

            metadata=(
                base_metadata
            ),

            embedding=(
                embedding
            ),

            is_active=True,
        )

    # -----------------------------------------------------
    # Text extraction
    # -----------------------------------------------------

    def _extract_question_text(
        self,
        question: dict[str, Any],
    ) -> str:
        """
        استخراج نص السؤال بدون الحل.
        """

        preferred_keys = [
            "text",
            "question",
            "statement",
            "prompt",
            "content",
            "instruction",
        ]

        parts = []

        for key in preferred_keys:

            if key not in question:
                continue

            value = question.get(key)

            text = self._extract_text(
                value
            )

            if text:
                parts.append(text)

        # إزالة التكرار
        return self._unique_join(
            parts
        )

    def _extract_text(
        self,
        value: Any,
    ) -> str:
        """
        استخراج النص من String / List / Dict.

        مفيد لأن JSON تمارين البكالوريا
        قد يختلف قليلًا بين تمرين وآخر.
        """

        if value is None:
            return ""

        # ---------------------------------------------
        # String
        # ---------------------------------------------

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        # ---------------------------------------------
        # Number
        # ---------------------------------------------

        if isinstance(
            value,
            (int, float),
        ):
            return str(value)

        # ---------------------------------------------
        # List
        # ---------------------------------------------

        if isinstance(
            value,
            list,
        ):

            parts = []

            for item in value:

                text = (
                    self._extract_text(
                        item
                    )
                )

                if text:
                    parts.append(text)

            return self._unique_join(
                parts
            )

        # ---------------------------------------------
        # Dict
        # ---------------------------------------------

        if isinstance(
            value,
            dict,
        ):

            parts = []

            # Ne pas mettre des informations
            # purement graphiques dans embedding.
            ignored_keys = {
                "graph",
                "graph_data",
                "statement_graph_data",
                "image",
                "images",
                "figure",
                "figures",
                "table",
                "tables",
                "react_data",
                "metadata",
            }

            for key, item in value.items():

                if key in ignored_keys:
                    continue

                text = (
                    self._extract_text(
                        item
                    )
                )

                if text:
                    parts.append(text)

            return self._unique_join(
                parts
            )

        return ""

    @staticmethod
    def _get_title(
        value: Any,
    ) -> str:

        if not isinstance(
            value,
            dict,
        ):
            return ""

        for key in (
            "title",
            "label",
            "name",
        ):

            title = value.get(key)

            if isinstance(
                title,
                str,
            ) and title.strip():
                return title.strip()

        return ""

    @staticmethod
    def _text(
        value: Any,
    ) -> str:

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        return ""

    @staticmethod
    def _unique_join(
        values: list[str],
    ) -> str:

        result = []

        seen = set()

        for value in values:

            normalized = (
                " ".join(
                    value.split()
                )
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            result.append(
                value.strip()
            )

        return "\n".join(
            result
        )