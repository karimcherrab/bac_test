import json
from pathlib import Path
from typing import Any

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from course.models import (
    Axis,
    Branch,
    Chapter,
    Subject,
)


class Command(BaseCommand):
    """
    Importe tous les fichiers JSON présents dans un dossier.

    Chaque fichier peut contenir :

    1. Un axe directement :

    {
        "tag": "...",
        "title": "...",
        "order": 1,
        "is_active": true,
        "branches": ["math", "science"],
        "content": {...}
    }

    2. Une liste d'axes :

    [
        {...},
        {...}
    ]

    3. Un objet avec une clé axes :

    {
        "axes": [
            {...},
            {...}
        ]
    }
    """

    help = (
        "Importe tous les fichiers JSON d'un dossier "
        "dans PostgreSQL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--folder",
            type=str,
            required=True,
            help=(
                "Chemin du dossier contenant "
                "les fichiers JSON."
            ),
        )

        parser.add_argument(
            "--subject-code",
            type=str,
            default="science",
            help=(
                "Code de la matière. "
                "Valeur par défaut : math."
            ),
        )

        parser.add_argument(
            "--subject-name",
            type=str,
            default="الفيزياء",
            help=(
                "Nom utilisé si la matière "
                "doit être créée."
            ),
        )

        parser.add_argument(
            "--chapter-code",
            type=str,
            default=None,
            help=(
                "Code du chapitre. S'il est absent, "
                "le programme essaie de le lire depuis "
                "content.chapter_code."
            ),
        )

        parser.add_argument(
            "--chapter-title",
            type=str,
            default=None,
            help=(
                "Titre du chapitre. S'il est absent, "
                "le programme utilise content.chapter_title."
            ),
        )

        parser.add_argument(
            "--chapter-order",
            type=int,
            default=1,
            help=(
                "Ordre du chapitre s'il doit "
                "être créé."
            ),
        )

        parser.add_argument(
            "--replace-content",
            action="store_true",
            help=(
                "Remplace complètement le contenu "
                "JSON existant de l'axe."
            ),
        )

        parser.add_argument(
            "--recursive",
            action="store_true",
            help=(
                "Cherche aussi les fichiers JSON "
                "dans les sous-dossiers."
            ),
        )

        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help=(
                "Continue l'import des autres fichiers "
                "lorsqu'un fichier contient une erreur."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Valide tous les fichiers sans "
                "enregistrer les données."
            ),
        )

    def handle(self, *args, **options):
        folder_path = (
            Path(options["folder"])
            .expanduser()
            .resolve()
        )

        if not folder_path.exists():
            raise CommandError(
                f"Dossier introuvable : {folder_path}"
            )

        if not folder_path.is_dir():
            raise CommandError(
                "Le chemin fourni n'est pas un dossier : "
                f"{folder_path}"
            )

        subject_code = options["subject_code"].strip()
        subject_name = options["subject_name"].strip()

        explicit_chapter_code = options[
            "chapter_code"
        ]

        explicit_chapter_title = options.get(
            "chapter_title"
        )

        if explicit_chapter_title:
            explicit_chapter_title = (
                explicit_chapter_title.strip()
            )

        chapter_order = options["chapter_order"]
        replace_content = options["replace_content"]
        recursive = options["recursive"]
        continue_on_error = options[
            "continue_on_error"
        ]
        dry_run = options["dry_run"]

        if explicit_chapter_code:
            explicit_chapter_code = (
                explicit_chapter_code.strip()
            )

        if not subject_code:
            raise CommandError(
                "Le code de la matière "
                "ne peut pas être vide."
            )

        if not subject_name:
            raise CommandError(
                "Le nom de la matière "
                "ne peut pas être vide."
            )

        json_files = self.get_json_files(
            folder_path=folder_path,
            recursive=recursive,
        )

        if not json_files:
            raise CommandError(
                "Aucun fichier JSON trouvé dans : "
                f"{folder_path}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(json_files)} fichier(s) JSON trouvé(s)."
            )
        )

        self.stdout.write("")

        total_created = 0
        total_updated = 0
        total_axes = 0
        successful_files = 0
        failed_files = 0

        for file_index, json_path in enumerate(
            json_files,
            start=1,
        ):
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"[{file_index}/{len(json_files)}] "
                    f"Traitement de : {json_path.name}"
                )
            )

            try:
                result = self.process_json_file(
                    json_path=json_path,
                    subject_code=subject_code,
                    subject_name=subject_name,
                    explicit_chapter_code=(
                        explicit_chapter_code
                    ),
                    explicit_chapter_title=explicit_chapter_title,
                    chapter_order=chapter_order,
                    replace_content=replace_content,
                    dry_run=dry_run,
                )

                total_created += result["created"]
                total_updated += result["updated"]
                total_axes += result["total"]
                successful_files += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Fichier traité : {json_path.name}"
                    )
                )

            except Exception as exc:
                failed_files += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"Erreur dans {json_path.name} : "
                        f"{exc}"
                    )
                )

                if not continue_on_error:
                    raise CommandError(
                        "Import arrêté à cause d'une erreur "
                        f"dans le fichier {json_path.name}."
                    ) from exc

            self.stdout.write("")

        self.stdout.write(
            "=" * 60
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Mode dry-run : aucune donnée "
                    "n'a été enregistrée."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Import du dossier terminé."
                )
            )

        self.stdout.write(
            f"Fichiers trouvés : {len(json_files)}"
        )

        self.stdout.write(
            f"Fichiers réussis : {successful_files}"
        )

        self.stdout.write(
            f"Fichiers échoués : {failed_files}"
        )

        self.stdout.write(
            f"Axes traités : {total_axes}"
        )

        self.stdout.write(
            f"Axes créés : {total_created}"
        )

        self.stdout.write(
            f"Axes mis à jour : {total_updated}"
        )

    def get_json_files(
        self,
        folder_path: Path,
        recursive: bool,
    ) -> list[Path]:
        """
        Retourne tous les fichiers JSON du dossier.

        recursive=False :
        uniquement le dossier principal.

        recursive=True :
        dossier principal et sous-dossiers.
        """

        if recursive:
            json_files = list(
                folder_path.rglob("*.json")
            )
        else:
            json_files = list(
                folder_path.glob("*.json")
            )

        json_files = [
            path
            for path in json_files
            if path.is_file()
        ]

        return sorted(
            json_files,
            key=lambda path: (
                path.parent.as_posix().lower(),
                path.name.lower(),
            ),
        )

    def process_json_file(
        self,
        json_path: Path,
        subject_code: str,
        subject_name: str,
        explicit_chapter_code: str | None,
        explicit_chapter_title: str | None,
        chapter_order: int,
        replace_content: bool,
        dry_run: bool,
    ) -> dict:
        """
        Lit, valide et importe un fichier JSON.
        """

        data = self.load_json(json_path)

        axes_data = self.extract_axes(
            data=data,
            filename=json_path.name,
        )

        if not axes_data:
            raise CommandError(
                f"Aucun axe trouvé dans {json_path.name}."
            )

        validated_axes = []

        for position, axis_data in enumerate(
            axes_data,
            start=1,
        ):
            validated_axis = self.validate_axis(
                axis_data=axis_data,
                position=position,
                filename=json_path.name,
            )

            validated_axes.append(
                validated_axis
            )

        all_branch_codes = sorted(
            {
                branch_code
                for axis_data in validated_axes
                for branch_code in axis_data[
                    "branches"
                ]
            }
        )

        branches_by_code = (
            self.get_branches_by_code(
                branch_codes=all_branch_codes,
                filename=json_path.name,
            )
        )

        if dry_run:
            for axis_data in validated_axes:
                branches_text = ", ".join(
                    axis_data["branches"]
                )

                self.stdout.write(
                    f"  - {axis_data['tag']} "
                    f"| {axis_data['title']} "
                    f"| branches : {branches_text}"
                )

            return {
                "created": 0,
                "updated": 0,
                "total": len(validated_axes),
            }

        created_count = 0
        updated_count = 0

        # Chaque fichier est traité dans sa propre transaction.
        # Si le fichier échoue, ses modifications sont annulées.
        with transaction.atomic():
            subject, subject_created = (
                Subject.objects.get_or_create(
                    code=subject_code,
                    defaults={
                        "name": subject_name,
                        "description": "",
                    },
                )
            )

            if subject_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        "  Matière créée : "
                        f"{subject.code} - {subject.name}"
                    )
                )

            for axis_data in validated_axes:
                result = self.save_axis(
                    axis_data=axis_data,
                    subject=subject,
                    branches_by_code=(
                        branches_by_code
                    ),
                    explicit_chapter_code=(
                        explicit_chapter_code
                    ),
                    explicit_chapter_title=explicit_chapter_title,
                    chapter_order=chapter_order,
                    replace_content=replace_content,
                )

                if result == "created":
                    created_count += 1

                if result == "updated":
                    updated_count += 1

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(validated_axes),
        }

    def save_axis(
        self,
        axis_data: dict,
        subject: Subject,
        branches_by_code: dict[str, Branch],
        explicit_chapter_code: str | None,
        explicit_chapter_title: str | None,
        chapter_order: int,
        replace_content: bool,
    ) -> str:
        """
        Crée ou met à jour un axe.
        """

        content = axis_data["content"]
        branch_codes = axis_data["branches"]

        chapter_code = (
            explicit_chapter_code
            or content.get("chapter_code")
        )

        if not chapter_code:
            raise CommandError(
                "Impossible de déterminer le chapitre "
                f"pour l'axe '{axis_data['tag']}'. "
                "Ajoute content.chapter_code ou utilise "
                "--chapter-code."
            )

        if not isinstance(chapter_code, str):
            raise CommandError(
                "Le chapter_code de l'axe "
                f"'{axis_data['tag']}' doit être une chaîne."
            )

        chapter_code = chapter_code.strip()

        if not chapter_code:
            raise CommandError(
                "Le chapter_code de l'axe "
                f"'{axis_data['tag']}' est vide."
            )

        content_chapter_title = content.get(
            "chapter_title"
        )

        chapter_title = (
            explicit_chapter_title
            or content_chapter_title
        )

        if not isinstance(chapter_title, str):
            raise CommandError(
                "Impossible de déterminer le titre du chapitre "
                f"pour l'axe '{axis_data['tag']}'. "
                "Ajoute content.chapter_title dans le JSON "
                "ou utilise --chapter-title."
            )

        chapter_title = chapter_title.strip()

        if not chapter_title:
            raise CommandError(
                "Le titre du chapitre est vide "
                f"pour l'axe '{axis_data['tag']}'."
            )

        chapter, chapter_created = (
            Chapter.objects.get_or_create(
                subject=subject,
                code=chapter_code,
                defaults={
                    "title": chapter_title,
                    "order": chapter_order,
                    "is_active": True,
                },
            )
        )

        if chapter_created:
            self.stdout.write(
                self.style.SUCCESS(
                    "  Chapitre créé : "
                    f"{chapter.code} - {chapter.title}"
                )
            )
        else:
            chapter_fields_to_update = []

            if chapter.title != chapter_title:
                chapter.title = chapter_title
                chapter_fields_to_update.append(
                    "title"
                )

            if (
                hasattr(chapter, "is_active")
                and not chapter.is_active
            ):
                chapter.is_active = True
                chapter_fields_to_update.append(
                    "is_active"
                )

            if chapter_fields_to_update:
                chapter.save(
                    update_fields=chapter_fields_to_update
                )

                self.stdout.write(
                    self.style.WARNING(
                        "  Chapitre mis à jour : "
                        f"{chapter.code} - {chapter.title}"
                    )
                )

        axis_branches = [
            branches_by_code[code]
            for code in branch_codes
        ]

        existing_axis = (
            Axis.objects
            .filter(
                chapter=chapter,
                tag=axis_data["tag"],
            )
            .first()
        )

        if existing_axis is None:
            axis = Axis.objects.create(
                chapter=chapter,
                tag=axis_data["tag"],
                title=axis_data["title"],
                order=axis_data["order"],
                is_active=axis_data["is_active"],
                content=content,
            )

            axis.branches.set(
                axis_branches
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "  Axe créé : "
                    f"{axis_data['tag']} "
                    f"| branches : "
                    f"{', '.join(branch_codes)}"
                )
            )

            return "created"

        if replace_content:
            final_content = content
        else:
            final_content = self.deep_merge(
                existing_axis.content or {},
                content,
            )

        existing_axis.title = axis_data["title"]
        existing_axis.order = axis_data["order"]
        existing_axis.is_active = (
            axis_data["is_active"]
        )
        existing_axis.content = final_content

        existing_axis.save(
            update_fields=[
                "title",
                "order",
                "is_active",
                "content",
            ]
        )

        existing_axis.branches.set(
            axis_branches
        )

        self.stdout.write(
            self.style.WARNING(
                "  Axe mis à jour : "
                f"{axis_data['tag']} "
                f"| branches : "
                f"{', '.join(branch_codes)}"
            )
        )

        return "updated"

    def load_json(
        self,
        json_path: Path,
    ) -> Any:
        """
        Lit un fichier JSON en UTF-8.
        """

        try:
            with json_path.open(
                mode="r",
                encoding="utf-8-sig",
            ) as file:
                return json.load(file)

        except UnicodeDecodeError as exc:
            raise CommandError(
                f"Le fichier {json_path.name} "
                "doit être encodé en UTF-8."
            ) from exc

        except json.JSONDecodeError as exc:
            raise CommandError(
                f"JSON invalide dans {json_path.name}, "
                f"ligne {exc.lineno}, "
                f"colonne {exc.colno} : "
                f"{exc.msg}"
            ) from exc

        except OSError as exc:
            raise CommandError(
                "Impossible de lire le fichier "
                f"{json_path.name} : {exc}"
            ) from exc

    def extract_axes(
        self,
        data: Any,
        filename: str,
    ) -> list[dict]:
        """
        Accepte :

        - un axe directement ;
        - une liste d'axes ;
        - un objet contenant la clé axes.
        """

        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            raise CommandError(
                f"La racine de {filename} doit être "
                "un objet ou une liste."
            )

        if "axes" in data:
            axes = data["axes"]

            if not isinstance(axes, list):
                raise CommandError(
                    f"La propriété 'axes' de {filename} "
                    "doit être une liste."
                )

            return axes

        if "tag" in data and "content" in data:
            return [data]

        raise CommandError(
            f"Structure JSON non reconnue dans {filename}. "
            "Le fichier doit contenir un axe, "
            "une liste d'axes ou une clé 'axes'."
        )

    def validate_axis(
        self,
        axis_data: Any,
        position: int,
        filename: str,
    ) -> dict:
        """
        Valide et normalise un axe.
        """

        if not isinstance(axis_data, dict):
            raise CommandError(
                f"L'axe numéro {position} de {filename} "
                "doit être un objet JSON."
            )

        tag = axis_data.get("tag")
        title = axis_data.get("title")
        content = axis_data.get("content")
        branches = axis_data.get("branches")

        if not isinstance(tag, str) or not tag.strip():
            raise CommandError(
                f"L'axe numéro {position} de {filename} "
                "ne possède pas de tag valide."
            )

        tag = tag.strip()

        if (
            not isinstance(title, str)
            or not title.strip()
        ):
            raise CommandError(
                f"L'axe '{tag}' de {filename} "
                "ne possède pas de titre valide."
            )

        title = title.strip()

        if not isinstance(content, dict):
            raise CommandError(
                f"Le champ content de l'axe '{tag}' "
                f"dans {filename} doit être un objet JSON."
            )

        if branches is None:
            raise CommandError(
                f"Le champ branches est obligatoire "
                f"pour l'axe '{tag}' dans {filename}."
            )

        if not isinstance(branches, list):
            raise CommandError(
                f"Le champ branches de l'axe '{tag}' "
                f"dans {filename} doit être une liste."
            )

        if not branches:
            raise CommandError(
                f"L'axe '{tag}' dans {filename} "
                "doit posséder au moins une branche."
            )

        normalized_branches = []

        for branch_position, branch_code in enumerate(
            branches,
            start=1,
        ):
            if (
                not isinstance(branch_code, str)
                or not branch_code.strip()
            ):
                raise CommandError(
                    f"La branche numéro {branch_position} "
                    f"de l'axe '{tag}' dans {filename} "
                    "n'est pas valide."
                )

            normalized_code = (
                branch_code.strip()
            )

            if (
                normalized_code
                not in normalized_branches
            ):
                normalized_branches.append(
                    normalized_code
                )

        order = axis_data.get(
            "order",
            0,
        )

        if (
            isinstance(order, bool)
            or not isinstance(order, int)
        ):
            raise CommandError(
                f"Le champ order de l'axe '{tag}' "
                f"dans {filename} doit être un entier."
            )

        if order < 0:
            raise CommandError(
                f"Le champ order de l'axe '{tag}' "
                f"dans {filename} ne peut pas être négatif."
            )

        is_active = axis_data.get(
            "is_active",
            True,
        )

        if not isinstance(is_active, bool):
            raise CommandError(
                f"Le champ is_active de l'axe '{tag}' "
                f"dans {filename} doit être un booléen."
            )

        content_axis_tag = content.get(
            "axis_tag"
        )

        if (
            content_axis_tag
            and content_axis_tag != tag
        ):
            raise CommandError(
                f"Incohérence dans {filename} pour "
                f"l'axe '{tag}' : content.axis_tag "
                f"vaut '{content_axis_tag}'."
            )

        content_axis_title = content.get(
            "axis_title"
        )

        if (
            content_axis_title
            and content_axis_title != title
        ):
            self.stdout.write(
                self.style.WARNING(
                    f"  Attention dans {filename} : "
                    f"le titre de '{tag}' est différent "
                    "de content.axis_title."
                )
            )

        return {
            "tag": tag,
            "title": title,
            "order": order,
            "is_active": is_active,
            "branches": normalized_branches,
            "content": content,
        }

    def get_branches_by_code(
        self,
        branch_codes: list[str],
        filename: str,
    ) -> dict[str, Branch]:
        """
        Vérifie que les branches existent.
        """

        branches = Branch.objects.filter(
            code__in=branch_codes,
        )

        branches_by_code = {
            branch.code: branch
            for branch in branches
        }

        missing_codes = [
            code
            for code in branch_codes
            if code not in branches_by_code
        ]

        if missing_codes:
            raise CommandError(
                "Les branches suivantes utilisées dans "
                f"{filename} n'existent pas : "
                f"{', '.join(missing_codes)}."
            )

        return branches_by_code

    def deep_merge(
        self,
        old_data: dict,
        new_data: dict,
    ) -> dict:
        """
        Fusionne récursivement deux dictionnaires.

        Les nouvelles valeurs remplacent les anciennes.
        Les nouvelles listes remplacent les anciennes listes.
        """

        result = old_data.copy()

        for key, new_value in new_data.items():
            old_value = result.get(key)

            if (
                isinstance(old_value, dict)
                and isinstance(new_value, dict)
            ):
                result[key] = self.deep_merge(
                    old_value,
                    new_value,
                )
            else:
                result[key] = new_value

        return result