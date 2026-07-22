import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from knowledge.models import (
    Chapter,
    Axis,
    KnowledgeItem,
    KnowledgeRelationship,
)


class Command(BaseCommand):
    help = "Ingest knowledge base files into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="Path to chapter folder, example: data/knowledge/sequences",
        )

    def handle(self, *args, **options):
        base_path = Path(options["path"])

        if not base_path.exists():
            raise CommandError(f"Path does not exist: {base_path}")

        chapter_code = base_path.name

        self.stdout.write(self.style.WARNING(f"Reading from: {base_path}"))

        with transaction.atomic():
            chapter = self.get_or_create_chapter(base_path, chapter_code)
            axes_count = self.ingest_axes_from_metadata(base_path, chapter)
            items_count = self.ingest_json_files(base_path, chapter)
            rel_count = self.ingest_knowledge_graph(base_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Axes: {axes_count}, Items: {items_count}, Relationships: {rel_count}"
            )
        )

    def get_or_create_chapter(self, base_path: Path, chapter_code: str) -> Chapter:
        metadata_file = base_path / "lesson" / "metadata.json"

        title = chapter_code
        subject = "math"
        branch = "science"

        if metadata_file.exists():
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = json.load(f)

            title = metadata.get("chapter", title)
            subject = metadata.get("subject", subject)
            branch = metadata.get("branch", branch)

        chapter, _ = Chapter.objects.update_or_create(
            code=chapter_code,
            defaults={
                "title": title,
                "subject": subject,
                "branch": branch,
            },
        )

        return chapter

    def ingest_axes_from_metadata(self, base_path: Path, chapter: Chapter) -> int:
        metadata_file = base_path / "lesson" / "metadata.json"

        if not metadata_file.exists():
            self.stdout.write(self.style.WARNING("No lesson/metadata.json found."))
            return 0

        with metadata_file.open("r", encoding="utf-8") as f:
            metadata = json.load(f)

        axes = metadata.get("axes", [])
        count = 0

        for index, axis_data in enumerate(axes, start=1):
            tag = axis_data.get("tag")
            title = axis_data.get("title")

            if not tag or not title:
                continue

            Axis.objects.update_or_create(
                tag=tag,
                defaults={
                    "chapter": chapter,
                    "title": title,
                    "order": index,
                    "source_file": metadata.get("source_file", ""),
                    "pages": axis_data.get("pages", []),
                    "metadata": axis_data,
                },
            )

            count += 1

        return count

    def ingest_json_files(self, base_path: Path, chapter: Chapter) -> int:
        count = 0

        for json_file in base_path.rglob("*.json"):
            if json_file.name.startswith("knowledge_graph"):
                continue

            if json_file.name == "metadata.json":
                continue

            self.stdout.write(f"Reading JSON: {json_file}")

            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if "tag" in data and "title" in data and "content" in data:
                count += self.ingest_lesson_axis(json_file, data, chapter)
                continue

            if "questions" in data:
                count += self.ingest_bac_exercise(json_file, data, chapter)
                continue

        return count

    def ingest_lesson_axis(self, json_file: Path, data: dict, chapter: Chapter) -> int:
        tag = data.get("tag")
        title = data.get("title")
        content = data.get("content", "")
        pages = data.get("pages", [])
        images = data.get("images", [])

        if not tag:
            return 0

        axis, _ = Axis.objects.get_or_create(
            tag=tag,
            defaults={
                "chapter": chapter,
                "title": title or tag,
                "source_file": data.get("source_file", ""),
                "pages": pages,
                "metadata": {
                    "tag": tag,
                    "json_path": str(json_file),
                },
            },
        )

        item_id = f"lesson::{chapter.code}::{tag}"

        KnowledgeItem.objects.update_or_create(
            id=item_id,
            defaults={
                "axis": axis,
                "title": title or tag,
                "item_type": "lesson",
                "subject": chapter.subject,
                "branch": chapter.branch,
                "chapter": chapter.code,
                "language": data.get("language", "ar"),
                "content": content,
                "summary": data.get("summary", ""),
                "difficulty": data.get("difficulty", ""),
                "concepts": data.get("concepts", []),
                "skills": data.get("skills", []),
                "keywords": data.get("keywords", [tag]),
                "source_file": data.get("source_file", json_file.name),
                "source_page": ",".join(map(str, pages)),
                "images": images,
                "metadata": {
                    **data,
                    "tag": tag,
                    "json_path": str(json_file),
                    "images": images,
                },
            },
        )

        return 1

    def ingest_bac_exercise(self, json_file: Path, data: dict, chapter: Chapter) -> int:
        year = data.get("year")
        exercise_title = data.get("exercise_title", "")
        source_file = data.get("source_file", json_file.name)
        page = data.get("page", "")
        points = data.get("points", "")

        count = 0

        for q in data.get("questions", []):
            question_number = q.get("number", "")
            tag = q.get("tag", "")
            question_text = q.get("text", "")
            images = q.get("images", [])

            if not tag:
                self.stdout.write(
                    self.style.WARNING(
                        f"No tag for question {question_number} in {json_file}"
                    )
                )
                continue

            axis = Axis.objects.filter(
                tag=tag,
                chapter=chapter
            ).first()

            if not axis:
                axis = Axis.objects.filter(tag=tag).first()

            if not axis:
                self.stdout.write(
                    self.style.ERROR(
                        f"Axis not found for tag={tag} | file={json_file}"
                    )
                )
                continue

            safe_exercise_title = (
                exercise_title.replace(" ", "_")
                .replace("/", "_")
                .replace("\\", "_")
            )

            item_id = (
                f"bac::{chapter.code}::{year}::"
                f"{safe_exercise_title}::q{question_number}"
            )

            KnowledgeItem.objects.update_or_create(
                id=item_id,
                defaults={
                    "axis": axis,
                    "title": f"{exercise_title} - السؤال {question_number}",
                    "item_type": "bac_question",
                    "subject": chapter.subject,
                    "branch": chapter.branch,
                    "chapter": chapter.code,
                    "language": "ar",
                    "content": question_text,
                    "summary": q.get("summary", ""),
                    "difficulty": q.get("difficulty", ""),
                    "concepts": q.get("concepts", []),
                    "skills": q.get("skills", []),
                    "keywords": q.get("keywords", [tag]),
                    "source_file": source_file,
                    "source_page": str(page),
                    "year": year,
                    "exercise_title": exercise_title,
                    "question_number": question_number,
                    "points": points,
                    "images": images,
                    "metadata": {
                        "source_file": source_file,
                        "year": year,
                        "page": page,
                        "exercise_title": exercise_title,
                        "points": points,
                        "question_number": question_number,
                        "tag": tag,
                        "axis_id": axis.id,
                        "axis_tag": axis.tag,
                        "axis_title": axis.title,
                        "images": images,
                        "json_path": str(json_file),
                    },
                },
            )

            count += 1

        return count

    def ingest_knowledge_graph(self, base_path: Path) -> int:
        graph_files = list(base_path.rglob("knowledge_graph*.json"))

        if not graph_files:
            self.stdout.write(
                self.style.WARNING("No knowledge_graph*.json file found.")
            )
            return 0

        total = 0

        for graph_file in graph_files:
            self.stdout.write(f"Reading graph: {graph_file}")

            with graph_file.open("r", encoding="utf-8") as f:
                graph = json.load(f)

            edges = graph.get("edges", [])

            for edge in edges:
                source_id = edge.get("source")
                target_id = edge.get("target")
                relation = edge.get("relation", "RELATED_TO")

                if not source_id or not target_id:
                    continue

                source = KnowledgeItem.objects.filter(id=source_id).first()
                target = KnowledgeItem.objects.filter(id=target_id).first()

                if not source or not target:
                    continue

                KnowledgeRelationship.objects.update_or_create(
                    source=source,
                    target=target,
                    relation_type=self.normalize_relation_type(relation),
                    defaults={"metadata": edge},
                )

                total += 1

        return total

    def normalize_relation_type(self, value: str) -> str:
        allowed = {
            "HAS_SKILL",
            "USES_METHOD",
            "USES_FORMULA",
            "SUPPORTED_BY",
            "HAS_EXAMPLE",
            "HAS_HINT",
            "COMMON_MISTAKE",
            "REQUIRES",
            "RELATED_TO",
            "BELONGS_TO_CONCEPT",
        }

        value = str(value).upper()
        return value if value in allowed else "RELATED_TO"