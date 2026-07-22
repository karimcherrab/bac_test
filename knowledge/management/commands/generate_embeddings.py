from django.core.management.base import BaseCommand
from django.db import transaction
from sentence_transformers import SentenceTransformer

from knowledge.models import KnowledgeItem, KnowledgeEmbedding


class Command(BaseCommand):
    help = "Generate local embeddings using BAAI/bge-m3"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--batch-size", type=int, default=16)
        parser.add_argument("--model", type=str, default="BAAI/bge-m3")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        limit = options["limit"]
        batch_size = options["batch_size"]
        model_name = options["model"]
        force = options["force"]

        self.stdout.write(self.style.WARNING(f"Loading model: {model_name}"))

        model = SentenceTransformer(model_name)

        if force:
            items = KnowledgeItem.objects.all()[:limit]
        else:
            items = KnowledgeItem.objects.filter(embedding__isnull=True)[:limit]

        items = list(items)

        self.stdout.write(
            self.style.WARNING(f"Items to process: {len(items)}")
        )

        if not items:
            self.stdout.write(self.style.SUCCESS("No items to embed."))
            return

        for start in range(0, len(items), batch_size):
            batch = items[start:start + batch_size]

            texts = []
            for item in batch:
                text = self.build_text(item)
                texts.append(text)

            vectors = model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=batch_size,
                show_progress_bar=False,
            )

            with transaction.atomic():
                for item, vector in zip(batch, vectors):
                    vector_list = vector.tolist()

                    KnowledgeEmbedding.objects.update_or_create(
                        item=item,
                        defaults={
                            "vector": vector_list,
                            "model_name": model_name,
                            "dimension": len(vector_list),
                        },
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"OK: {item.id} | dim={len(vector_list)}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS("Embeddings generated successfully."))

    def build_text(self, item: KnowledgeItem) -> str:
        axis = item.axis
        tag = axis.tag if axis else item.metadata.get("tag", "")
        axis_title = axis.title if axis else ""

        parts = [
            f"العنوان: {item.title}",
            f"النوع: {item.item_type}",
            f"المادة: {item.subject}",
            f"الشعبة: {item.branch}",
            f"الفصل: {item.chapter}",
            f"المحور: {axis_title}",
            f"tag: {tag}",
            "",
        ]

        if item.item_type == "bac_question":
            parts.extend([
                f"السنة: {item.year or item.metadata.get('year', '')}",
                f"التمرين: {item.exercise_title}",
                f"رقم السؤال: {item.question_number}",
                f"النقاط: {item.points}",
                "",
            ])

        if item.summary:
            parts.extend([
                "الملخص:",
                item.summary,
                "",
            ])

        parts.extend([
            "المحتوى:",
            item.content or "",
        ])

        if item.concepts:
            parts.extend([
                "",
                "المفاهيم: " + ", ".join(item.concepts),
            ])

        if item.skills:
            parts.extend([
                "",
                "المهارات: " + ", ".join(item.skills),
            ])

        if item.keywords:
            parts.extend([
                "",
                "الكلمات المفتاحية: " + ", ".join(item.keywords),
            ])

        # if item.images:
        #     parts.extend([
        #         "",
        #         "الصور: " + ", ".join(item.images),
        #     ])

        text = "\n".join(parts)
        return text[:16000]