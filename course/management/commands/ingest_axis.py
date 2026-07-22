import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from course.models import Subject, Axis, Chapter


class Command(BaseCommand):
    """
    Importe un ou plusieurs axes depuis un fichier JSON.

    Le fichier peut contenir :
    1. Un seul axe :
       {
           "tag": "...",
           "title": "...",
           "order": 1,
           "is_active": true,
           "content": {...}
       }

    2. Une liste d'axes :
       [
           {...},
           {...}
       ]

    3. Un objet contenant une clé "axes" :
       {
           "axes": [
               {...},
               {...}
           ]
       }
    """

    help = "Importe les données d'un ou plusieurs axes dans PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Chemin du fichier JSON à importer.",
        )

        parser.add_argument(
            "--subject-code",
            type=str,
            default="math",
            help="Code de la matière. Valeur par défaut : math.",
        )

        parser.add_argument(
            "--subject-name",
            type=str,
            default="الرياضيات",
            help="Nom utilisé si la matière doit être créée.",
        )

        parser.add_argument(
            "--chapter-code",
            type=str,
            default=None,
            help=(
                "Code du chapitre. S'il est absent, le programme essaie "
                "de le lire depuis content.chapter_code."
            ),
        )

        parser.add_argument(
            "--chapter-title",
            type=str,
            default="المتتاليات العددية",
            help="Titre utilisé si le chapitre doit être créé.",
        )

        parser.add_argument(
            "--chapter-order",
            type=int,
            default=1,
            help="Ordre du chapitre s'il doit être créé.",
        )

        parser.add_argument(
            "--replace-content",
            action="store_true",
            help="Remplace entièrement le contenu existant de l'axe.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valide les données sans les enregistrer.",
        )

    def handle(self, *args, **options):
        json_path = Path(options["file"]).expanduser().resolve()

        if not json_path.exists():
            raise CommandError(f"Fichier introuvable : {json_path}")

        if not json_path.is_file():
            raise CommandError(
                f"Le chemin fourni n'est pas un fichier : {json_path}"
            )

        data = self.load_json(json_path)
        axes_data = self.extract_axes(data)

        if not axes_data:
            raise CommandError("Aucun axe n'a été trouvé dans le fichier JSON.")

        subject_code = options["subject_code"].strip()
        subject_name = options["subject_name"].strip()
        explicit_chapter_code = options["chapter_code"]
        chapter_title = options["chapter_title"].strip()
        chapter_order = options["chapter_order"]
        replace_content = options["replace_content"]
        dry_run = options["dry_run"]

        validated_axes = []

        for index, axis_data in enumerate(axes_data, start=1):
            validated_axes.append(
                self.validate_axis(
                    axis_data=axis_data,
                    position=index,
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Validation réussie : {len(validated_axes)} axe(s). "
                    "Aucune donnée n'a été enregistrée."
                )
            )

            for axis_data in validated_axes:
                self.stdout.write(
                    f"- {axis_data['tag']} : {axis_data['title']}"
                )

            return

        with transaction.atomic():
            subject, subject_created = Subject.objects.get_or_create(
                code=subject_code,
                defaults={
                    "name": subject_name,
                    "description": "",
                },
            )

            if subject_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Matière créée : {subject.code} - {subject.name}"
                    )
                )

            created_count = 0
            updated_count = 0

            for axis_data in validated_axes:
                content = axis_data["content"]

                chapter_code = (
                    explicit_chapter_code
                    or content.get("chapter_code")
                )

                if not chapter_code:
                    raise CommandError(
                        f"Impossible de déterminer le chapitre pour "
                        f"l'axe '{axis_data['tag']}'. "
                        "Ajoute content.chapter_code dans le JSON ou utilise "
                        "--chapter-code."
                    )

                chapter, chapter_created = Chapter.objects.get_or_create(
                    subject=subject,
                    code=chapter_code,
                    defaults={
                        "title": chapter_title,
                        "order": chapter_order,
                        "is_active": True,
                    },
                )

                if chapter_created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Chapitre créé : {chapter.code} - {chapter.title}"
                        )
                    )

                existing_axis = Axis.objects.filter(
                    chapter=chapter,
                    tag=axis_data["tag"],
                ).first()

                if existing_axis is None:
                    Axis.objects.create(
                        chapter=chapter,
                        tag=axis_data["tag"],
                        title=axis_data["title"],
                        order=axis_data["order"],
                        is_active=axis_data["is_active"],
                        content=content,
                    )

                    created_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Axe créé : {axis_data['tag']}"
                        )
                    )

                    continue

                if replace_content:
                    final_content = content
                else:
                    final_content = self.deep_merge(
                        existing_axis.content or {},
                        content,
                    )

                existing_axis.title = axis_data["title"]
                existing_axis.order = axis_data["order"]
                existing_axis.is_active = axis_data["is_active"]
                existing_axis.content = final_content

                existing_axis.save(
                    update_fields=[
                        "title",
                        "order",
                        "is_active",
                        "content",
                    ]
                )

                updated_count += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Axe mis à jour : {axis_data['tag']}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Import terminé avec succès."
            )
        )
        self.stdout.write(f"Axes créés : {created_count}")
        self.stdout.write(f"Axes mis à jour : {updated_count}")
        self.stdout.write(f"Total traité : {len(validated_axes)}")

    def load_json(self, json_path: Path) -> Any:
        """
        Lit et décode le fichier JSON.
        """

        try:
            with json_path.open(
                mode="r",
                encoding="utf-8-sig",
            ) as file:
                return json.load(file)

        except UnicodeDecodeError as exc:
            raise CommandError(
                "Le fichier doit être encodé en UTF-8."
            ) from exc

        except json.JSONDecodeError as exc:
            raise CommandError(
                "JSON invalide dans le fichier "
                f"{json_path.name}, ligne {exc.lineno}, "
                f"colonne {exc.colno} : {exc.msg}"
            ) from exc

    def extract_axes(self, data: Any) -> list[dict]:
        """
        Accepte trois structures différentes :
        - un axe directement ;
        - une liste d'axes ;
        - un objet contenant la propriété axes.
        """

        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            raise CommandError(
                "La racine du JSON doit être un objet ou une liste."
            )

        if "axes" in data:
            axes = data["axes"]

            if not isinstance(axes, list):
                raise CommandError(
                    "La propriété 'axes' doit être une liste."
                )

            return axes

        if "tag" in data and "content" in data:
            return [data]

        raise CommandError(
            "Structure JSON non reconnue. "
            "Le fichier doit contenir un axe, une liste d'axes "
            "ou une propriété 'axes'."
        )

    def validate_axis(
        self,
        axis_data: Any,
        position: int,
    ) -> dict:
        """
        Valide et normalise les données d'un axe.
        """

        if not isinstance(axis_data, dict):
            raise CommandError(
                f"L'axe numéro {position} doit être un objet JSON."
            )

        tag = axis_data.get("tag")
        title = axis_data.get("title")
        content = axis_data.get("content")

        if not isinstance(tag, str) or not tag.strip():
            raise CommandError(
                f"L'axe numéro {position} ne possède pas de tag valide."
            )

        if not isinstance(title, str) or not title.strip():
            raise CommandError(
                f"L'axe '{tag}' ne possède pas de titre valide."
            )

        if not isinstance(content, dict):
            raise CommandError(
                f"Le champ content de l'axe '{tag}' doit être un objet JSON."
            )

        order = axis_data.get("order", 0)

        if isinstance(order, bool) or not isinstance(order, int):
            raise CommandError(
                f"Le champ order de l'axe '{tag}' doit être un entier."
            )

        if order < 0:
            raise CommandError(
                f"Le champ order de l'axe '{tag}' ne peut pas être négatif."
            )

        is_active = axis_data.get("is_active", True)

        if not isinstance(is_active, bool):
            raise CommandError(
                f"Le champ is_active de l'axe '{tag}' doit être un booléen."
            )

        content_axis_tag = content.get("axis_tag")

        if content_axis_tag and content_axis_tag != tag:
            raise CommandError(
                f"Incohérence pour l'axe '{tag}' : "
                f"content.axis_tag vaut '{content_axis_tag}'."
            )

        content_axis_title = content.get("axis_title")

        if content_axis_title and content_axis_title != title:
            self.stdout.write(
                self.style.WARNING(
                    f"Attention : le titre principal de '{tag}' est "
                    f"différent de content.axis_title."
                )
            )

        return {
            "tag": tag.strip(),
            "title": title.strip(),
            "order": order,
            "is_active": is_active,
            "content": content,
        }

    def deep_merge(
        self,
        old_data: dict,
        new_data: dict,
    ) -> dict:
        """
        Fusionne récursivement deux dictionnaires.

        Les nouvelles valeurs remplacent les anciennes.
        Pour les listes, la nouvelle liste remplace l'ancienne.
        """

        result = old_data.copy()

        for key, new_value in new_data.items():
            old_value = result.get(key)

            if isinstance(old_value, dict) and isinstance(new_value, dict):
                result[key] = self.deep_merge(
                    old_value,
                    new_value,
                )
            else:
                result[key] = new_value

        return result