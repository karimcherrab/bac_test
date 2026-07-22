import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import KnowledgeItem, KnowledgeRelationship


class Command(BaseCommand):
    help = "Ingest knowledge base files into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="Path to the knowledge base folder",
        )

    def handle(self, *args, **options):
        base_path = Path(options["path"])

        if not base_path.exists():
            raise CommandError(f"Path does not exist: {base_path}")

        self.stdout.write(self.style.WARNING(f"Reading from: {base_path}"))

        with transaction.atomic():
            items_count = self.ingest_jsonl_files(base_path)
            rel_count = self.ingest_knowledge_graph(base_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Items: {items_count}, Relationships: {rel_count}"
            )
        )

    def ingest_jsonl_files(self, base_path: Path) -> int:
        count = 0

        for jsonl_file in base_path.rglob("*.jsonl"):
            self.stdout.write(f"Reading JSONL: {jsonl_file}")

            with jsonl_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    data = json.loads(line)

                    item_id = data.get("id")
                    text = data.get("text", "")
                    metadata = data.get("metadata", {})

                    if not item_id:
                        continue

                    title = (
                        metadata.get("title")
                        or metadata.get("arabic_name")
                        or metadata.get("name")
                        or item_id
                    )

                    item_type = self.normalize_item_type(
                        metadata.get("type")
                        or metadata.get("content_type")
                        or metadata.get("chunk_kind")
                    )

                    KnowledgeItem.objects.update_or_create(
                        id=item_id,
                        defaults={
                            "title": title,
                            "item_type": item_type,
                            "subject": metadata.get("subject", "math"),
                            "branch": metadata.get("branch", "science"),
                            "chapter": metadata.get("chapter", "sequences"),
                            "language": metadata.get("language", "ar"),
                            "content": text,
                            "summary": metadata.get("summary", ""),
                            "difficulty": metadata.get("difficulty", ""),
                            "concepts": metadata.get("concepts", []),
                            "skills": metadata.get("skills", []),
                            "keywords": metadata.get("keywords", []),
                            "source_file": metadata.get("source_file", ""),
                            "source_page": str(
                                metadata.get("source_page")
                                or metadata.get("source_pages")
                                or ""
                            ),
                            "metadata": metadata,
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

            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])

            for node in nodes:
                node_id = node.get("id")
                if not node_id:
                    continue

                KnowledgeItem.objects.update_or_create(
                    id=node_id,
                    defaults={
                        "title": node.get("name", node_id),
                        "item_type": self.normalize_item_type(node.get("type")),
                        "subject": "math",
                        "branch": "science",
                        "chapter": "sequences",
                        "language": "ar",
                        "content": node.get("name", node_id),
                        "keywords": node.get("tags", []),
                        "metadata": node,
                    },
                )

            for edge in edges:
                source_id = edge.get("source")
                target_id = edge.get("target")
                relation = edge.get("relation", "RELATED_TO")

                if not source_id or not target_id:
                    continue

                source = KnowledgeItem.objects.filter(id=source_id).first()
                target = KnowledgeItem.objects.filter(id=target_id).first()

                if not source or not target:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping edge {source_id} -> {target_id}: missing node"
                        )
                    )
                    continue

                KnowledgeRelationship.objects.update_or_create(
                    source=source,
                    target=target,
                    relation_type=self.normalize_relation_type(relation),
                    defaults={
                        "metadata": edge,
                    },
                )

                total += 1

        return total

    def normalize_item_type(self, value: str) -> str:
        if not value:
            return "lesson"

        value = str(value).lower()

        mapping = {
            "bac_exercise": "bac_question",
            "bac_question": "bac_question",
            "question": "bac_question",
            "method": "method",
            "concept": "concept",
            "theorem": "theorem",
            "definition": "definition",
            "formula": "formula",
            "example": "example",
            "skill": "skill",
            "roadmap": "roadmap",
            "hint": "hint",
            "common_mistake": "mistake",
            "mistake": "mistake",
            "lesson": "lesson",
            "lesson_intro": "lesson",
            "solved_exercise": "example",
            "worked_example": "example",
            "application": "example",
            "rag_summary": "lesson",
            "full_solution": "bac_question",
            "solution": "bac_question",
        }

        return mapping.get(value, "lesson")

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

        if value in allowed:
            return value

        return "RELATED_TO"