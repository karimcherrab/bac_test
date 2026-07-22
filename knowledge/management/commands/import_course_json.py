import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import Chapter, Axis, KnowledgeItem


class Command(BaseCommand):
    """
    Importe un cours JSON dans:
    - Chapter
    - Axis
    - KnowledgeItem

    Deux formats sont supportés:

    FORMAT 1:
    {
        "chapter": "...",
        "chapter_code": "...",
        "tag": "...",
        "title": "...",
        "content": {...}
    }

    FORMAT 2:
    {
        "chapter": "...",
        "chapter_code": "...",
        "axis": {...},
        "lesson": {...}
    }
    """

    help = "Import a lesson JSON file into Chapter, Axis and KnowledgeItem"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to the lesson JSON file",
        )

    def handle(self, *args, **options):
        json_path = Path(options["file"]).expanduser().resolve()

        if not json_path.exists():
            raise CommandError(f"File not found: {json_path}")

        if not json_path.is_file():
            raise CommandError(f"Path is not a file: {json_path}")

        try:
            with json_path.open("r", encoding="utf-8-sig") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise CommandError(
                f"Invalid JSON at line {exc.lineno}, "
                f"column {exc.colno}: {exc.msg}"
            ) from exc

        normalized = self.normalize_document(data, json_path)

        with transaction.atomic():
            chapter = self.upsert_chapter(normalized)
            axis = self.upsert_axis(normalized, chapter)
            item = self.upsert_lesson(
                normalized=normalized,
                chapter=chapter,
                axis=axis,
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Course inserted successfully\n"
                f"Chapter: {chapter.code} - {chapter.title}\n"
                f"Axis: {axis.tag} - {axis.title}\n"
                f"KnowledgeItem: {item.id}"
            )
        )

    # ============================================================
    # NORMALISATION DES DEUX FORMATS JSON
    # ============================================================

    def normalize_document(
        self,
        data: Any,
        json_path: Path,
    ) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise CommandError("The JSON root must be an object.")

        chapter_title = self.clean_string(data.get("chapter"))
        chapter_code = self.clean_string(data.get("chapter_code"))

        if not chapter_title:
            raise CommandError("Missing required field: chapter")

        if not chapter_code:
            raise CommandError("Missing required field: chapter_code")

        # Nouveau format:
        # {
        #   "axis": {...},
        #   "lesson": {...}
        # }
        if isinstance(data.get("axis"), dict) and isinstance(
            data.get("lesson"),
            dict,
        ):
            return self.normalize_new_format(data, json_path)

        # Ancien format:
        # {
        #   "tag": "...",
        #   "title": "...",
        #   "content": {...}
        # }
        if all(key in data for key in ("tag", "title", "content")):
            return self.normalize_old_format(data, json_path)

        raise CommandError(
            "Unsupported JSON structure. Expected either:\n"
            "1. top-level fields: tag, title, content\n"
            "or\n"
            "2. top-level objects: axis, lesson"
        )

    def normalize_new_format(
        self,
        data: dict[str, Any],
        json_path: Path,
    ) -> dict[str, Any]:
        axis_data = data.get("axis", {})
        lesson_data = data.get("lesson", {})

        tag = self.clean_string(axis_data.get("tag"))
        axis_title = self.clean_string(axis_data.get("title"))
        lesson_title = self.clean_string(
            lesson_data.get("title")
            or axis_title
        )

        if not tag:
            raise CommandError("Missing required field: axis.tag")

        if not axis_title:
            raise CommandError("Missing required field: axis.title")

        if not lesson_title:
            raise CommandError("Missing required field: lesson.title")

        source_reference = axis_data.get("source_reference", {})
        if not isinstance(source_reference, dict):
            source_reference = {}

        pages = self.normalize_list(
            source_reference.get("reference_pages")
            or source_reference.get("pages")
            or axis_data.get("pages")
            or data.get("source_pages")
        )

        source_file = self.clean_string(
            source_reference.get("source_pdf")
            or source_reference.get("title")
            or data.get("source", {}).get("source_pdf")
            if isinstance(data.get("source"), dict)
            else ""
        )

        if not source_file:
            source_file = json_path.name

        return {
            "chapter_title": self.clean_string(data.get("chapter")),
            "chapter_code": self.clean_string(data.get("chapter_code")),
            "chapter_order": self.to_int(
                data.get("chapter_order"),
                default=0,
            ),
            "subject": self.clean_string(
                data.get("subject")
                or "math"
            ),
            "branch": self.clean_string(
                data.get("branch")
                or "science"
            ),
            "language": self.clean_string(
                data.get("language")
                or axis_data.get("language")
                or "ar"
            ),
            "direction": self.clean_string(
                data.get("direction")
                or axis_data.get("direction")
                or "rtl"
            ),
            "math_format": self.clean_string(
                data.get("math_format")
                or axis_data.get("math_format")
                or "LaTeX"
            ),
            "axis_order": self.to_int(
                axis_data.get("order"),
                default=0,
            ),
            "tag": tag,
            "axis_title": axis_title,
            "lesson_title": lesson_title,
            "difficulty": self.clean_string(
                axis_data.get("difficulty")
                or lesson_data.get("difficulty")
            ),
            "source_file": source_file,
            "source_pages": pages,
            "source": source_reference,
            "lesson_content": lesson_data,
            "summary": self.extract_summary(lesson_data),
            "concepts": self.extract_concepts(lesson_data),
            "skills": self.extract_skills(lesson_data),
            "keywords": self.extract_keywords(
                tag=tag,
                axis_title=axis_title,
                lesson_title=lesson_title,
                lesson_data=lesson_data,
            ),
            "images": self.normalize_list(
                lesson_data.get("images")
                or data.get("assets")
            ),
            "metadata": {
                "schema_version": "lesson_v2",
                "axis": axis_data,
                "lesson_goal": lesson_data.get("lesson_goal", ""),
                "subtitle": lesson_data.get("subtitle", ""),
                "estimated_duration_minutes": axis_data.get(
                    "estimated_duration_minutes"
                ),
                "json_path": str(json_path),
                "raw_document": data,
            },
        }

    def normalize_old_format(
        self,
        data: dict[str, Any],
        json_path: Path,
    ) -> dict[str, Any]:
        tag = self.clean_string(data.get("tag"))
        title = self.clean_string(data.get("title"))
        content = data.get("content")

        if not tag:
            raise CommandError("Missing required field: tag")

        if not title:
            raise CommandError("Missing required field: title")

        if not isinstance(content, dict):
            raise CommandError("'content' must be a JSON object.")

        source = data.get("source", {})
        if not isinstance(source, dict):
            source = {}

        pages = self.normalize_list(data.get("source_pages"))

        return {
            "chapter_title": self.clean_string(data.get("chapter")),
            "chapter_code": self.clean_string(data.get("chapter_code")),
            "chapter_order": self.to_int(
                data.get("chapter_order"),
                default=0,
            ),
            "subject": self.clean_string(
                data.get("subject")
                or "math"
            ),
            "branch": self.clean_string(
                data.get("branch")
                or "science"
            ),
            "language": self.clean_string(
                data.get("language")
                or "ar"
            ),
            "direction": self.clean_string(
                data.get("direction")
                or "rtl"
            ),
            "math_format": self.clean_string(
                data.get("math_format")
                or "LaTeX"
            ),
            "axis_order": self.to_int(
                data.get("axis_order"),
                default=0,
            ),
            "tag": tag,
            "axis_title": title,
            "lesson_title": title,
            "difficulty": self.clean_string(
                data.get("difficulty")
            ),
            "source_file": self.clean_string(
                source.get("source_pdf")
                or json_path.name
            ),
            "source_pages": pages,
            "source": source,
            "lesson_content": content,
            "summary": self.extract_old_summary(content),
            "concepts": self.extract_old_concepts(content),
            "skills": self.normalize_string_list(
                data.get("skills")
            ),
            "keywords": self.unique_strings(
                [
                    tag,
                    title,
                    *self.extract_old_concepts(content),
                    *self.normalize_string_list(
                        data.get("keywords")
                    ),
                ]
            ),
            "images": self.normalize_list(
                data.get("assets")
                or data.get("images")
            ),
            "metadata": {
                "schema_version": "lesson_v1",
                "merged_from_original_axes": data.get(
                    "merged_from_original_axes",
                    [],
                ),
                "editorial_notes": data.get(
                    "editorial_notes",
                    [],
                ),
                "json_path": str(json_path),
                "raw_document": data,
            },
        }

    # ============================================================
    # INSERTION EN BASE DE DONNEES
    # ============================================================

    def upsert_chapter(
        self,
        normalized: dict[str, Any],
    ) -> Chapter:
        chapter, created = Chapter.objects.update_or_create(
            code=normalized["chapter_code"],
            defaults={
                "title": normalized["chapter_title"],
                "subject": normalized["subject"] or "math",
                "branch": normalized["branch"] or "science",
                "order": normalized["chapter_order"],
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} chapter: {chapter.code}"
            )
        )

        return chapter

    def upsert_axis(
        self,
        normalized: dict[str, Any],
        chapter: Chapter,
    ) -> Axis:
        axis, created = Axis.objects.update_or_create(
            tag=normalized["tag"],
            defaults={
                "chapter": chapter,
                "title": normalized["axis_title"],
                "order": normalized["axis_order"],
                "source_file": normalized["source_file"],
                "pages": normalized["source_pages"],
                "metadata": {
                    "source": normalized["source"],
                    "direction": normalized["direction"],
                    "math_format": normalized["math_format"],
                    "difficulty": normalized["difficulty"],
                    **normalized["metadata"],
                },
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} axis: {axis.tag}"
            )
        )

        return axis

    def upsert_lesson(
        self,
        normalized: dict[str, Any],
        chapter: Chapter,
        axis: Axis,
    ) -> KnowledgeItem:
        item_id = (
            f"lesson::{chapter.code}::{normalized['tag']}"
        )

        # KnowledgeItem.content est un TextField.
        # On transforme donc le dictionnaire en chaîne JSON.
        content_text = json.dumps(
            normalized["lesson_content"],
            ensure_ascii=False,
            indent=2,
        )

        item, created = KnowledgeItem.objects.update_or_create(
            id=item_id,
            defaults={
                "axis": axis,
                "title": normalized["lesson_title"],
                "item_type": "lesson",
                "subject": chapter.subject,
                "branch": chapter.branch,
                "chapter": chapter.code,
                "language": normalized["language"] or "ar",
                "content": content_text,
                "summary": normalized["summary"],
                "difficulty": normalized["difficulty"],
                "concepts": normalized["concepts"],
                "skills": normalized["skills"],
                "keywords": normalized["keywords"],
                "source_file": normalized["source_file"],
                "source_page": ",".join(
                    str(page)
                    for page in normalized["source_pages"]
                ),
                "images": normalized["images"],
                "metadata": {
                    "schema_version": normalized[
                        "metadata"
                    ].get(
                        "schema_version",
                        "lesson",
                    ),
                    "chapter_title": normalized[
                        "chapter_title"
                    ],
                    "chapter_code": normalized[
                        "chapter_code"
                    ],
                    "axis_order": normalized[
                        "axis_order"
                    ],
                    "tag": normalized["tag"],
                    "axis_title": normalized[
                        "axis_title"
                    ],
                    "lesson_title": normalized[
                        "lesson_title"
                    ],
                    "direction": normalized[
                        "direction"
                    ],
                    "math_format": normalized[
                        "math_format"
                    ],
                    "source": normalized["source"],
                    "source_pages": normalized[
                        "source_pages"
                    ],
                    **normalized["metadata"],
                },
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} lesson: {item.id}"
            )
        )

        return item

    # ============================================================
    # EXTRACTION DES DONNEES DU COURS
    # ============================================================

    def extract_summary(
        self,
        lesson_data: dict[str, Any],
    ) -> str:
        lesson_goal = self.clean_string(
            lesson_data.get("lesson_goal")
        )
        if lesson_goal:
            return lesson_goal

        lesson_summary = lesson_data.get("lesson_summary")
        if isinstance(lesson_summary, dict):
            key_ideas = lesson_summary.get("key_ideas")
            if isinstance(key_ideas, list):
                return " ".join(
                    self.clean_string(item)
                    for item in key_ideas
                    if self.clean_string(item)
                )

        return self.clean_string(
            lesson_data.get("subtitle")
        )

    def extract_concepts(
        self,
        lesson_data: dict[str, Any],
    ) -> list[str]:
        concepts = []

        sections = lesson_data.get("sections", [])
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue

                title = self.clean_string(
                    section.get("title")
                )
                if title:
                    concepts.append(title)

        return self.unique_strings(concepts)

    def extract_skills(
        self,
        lesson_data: dict[str, Any],
    ) -> list[str]:
        skills = lesson_data.get("learning_outcomes")
        return self.normalize_string_list(skills)

    def extract_keywords(
        self,
        tag: str,
        axis_title: str,
        lesson_title: str,
        lesson_data: dict[str, Any],
    ) -> list[str]:
        concepts = self.extract_concepts(lesson_data)

        return self.unique_strings(
            [
                tag,
                axis_title,
                lesson_title,
                *concepts,
                *self.normalize_string_list(
                    lesson_data.get("keywords")
                ),
            ]
        )

    def extract_old_concepts(
        self,
        content: dict[str, Any],
    ) -> list[str]:
        concepts = []

        sections = content.get("sections", [])
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue

                title = self.clean_string(
                    section.get("title")
                )
                if title:
                    concepts.append(title)

        return self.unique_strings(concepts)

    def extract_old_summary(
        self,
        content: dict[str, Any],
    ) -> str:
        concepts = self.extract_old_concepts(content)

        if not concepts:
            return ""

        return "يتضمن الدرس: " + "، ".join(concepts) + "."

    # ============================================================
    # HELPERS
    # ============================================================

    def clean_string(self, value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def normalize_list(self, value: Any) -> list[Any]:
        if value is None or value == "":
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        return [value]

    def normalize_string_list(
        self,
        value: Any,
    ) -> list[str]:
        return self.unique_strings(
            self.normalize_list(value)
        )

    def unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:
        result = []
        seen = set()

        for value in values:
            text = self.clean_string(value)

            if not text or text in seen:
                continue

            seen.add(text)
            result.append(text)

        return result

    def to_int(
        self,
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default