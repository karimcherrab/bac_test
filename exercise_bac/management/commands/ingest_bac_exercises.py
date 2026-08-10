import json
import re
from pathlib import Path
from typing import Any

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import connection, transaction

from course.models import Branch, Chapter
from exercise_bac.models import ExerciseBac


class ExerciseJSONValidationError(Exception):
    """
    Erreur levée lorsqu'un fichier JSON ne respecte pas
    la structure attendue.
    """


class Command(BaseCommand):
    help = (
        "Lit les fichiers JSON d'un dossier et insère "
        "les exercices dans ExerciseBac avec leurs filières."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "folder",
            type=str,
            help=(
                "Chemin du dossier contenant les fichiers JSON."
            ),
        )

        parser.add_argument(
            "--update",
            action="store_true",
            help=(
                "Met à jour un exercice existant si son code "
                "existe déjà."
            ),
        )

        parser.add_argument(
            "--recursive",
            action="store_true",
            help=(
                "Recherche également les fichiers JSON dans "
                "les sous-dossiers."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Valide les fichiers sans écrire dans la base "
                "de données."
            ),
        )

        parser.add_argument(
            "--stop-on-error",
            action="store_true",
            help=(
                "Arrête complètement l'importation dès la "
                "première erreur."
            ),
        )

        parser.add_argument(
            "--chapter-code",
            type=str,
            default=None,
            help=(
                "Override optionnel du chapitre pour tous les fichiers. "
                "Sans cette option, chaque fichier utilise son propre "
                "champ chapter_code."
            ),
        )

        parser.add_argument(
            "--create-missing-branches",
            action="store_true",
            help=(
                "Crée automatiquement les filières absentes "
                "en utilisant les noms présents dans le JSON."
            ),
        )

    def handle(self, *args, **options):
        folder = Path(options["folder"]).resolve()

        update_existing = options["update"]
        recursive = options["recursive"]
        dry_run = options["dry_run"]
        stop_on_error = options["stop_on_error"]
        create_missing_branches = options[
            "create_missing_branches"
        ]
        chapter_code_override = options.get("chapter_code")
        if isinstance(chapter_code_override, str):
            chapter_code_override = chapter_code_override.strip() or None

        if not folder.exists():
            raise CommandError(
                f"Le dossier n'existe pas : {folder}"
            )

        if not folder.is_dir():
            raise CommandError(
                f"Le chemin n'est pas un dossier : {folder}"
            )

        # Le chapitre n'est plus résolu globalement ici.
        # Par défaut, chaque JSON choisit son chapitre via chapter_code.
        # --chapter-code reste disponible uniquement comme override global.

        # Vérifie avant l'import que la table intermédiaire
        # du ManyToManyField ExerciseBac.branches existe.
        self.ensure_branches_relation_ready()

        pattern = "**/*.json" if recursive else "*.json"

        json_files = sorted(folder.glob(pattern))
        json_files = [
            file_path
            for file_path in json_files
            if file_path.name.lower() != "manifest.json"
        ]

        if not json_files:
            raise CommandError(
                f"Aucun fichier JSON trouvé dans : {folder}"
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"{len(json_files)} fichier(s) JSON trouvé(s)."
            )
        )

        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "validated": 0,
            "branches_created": 0,
        }

        for json_file in json_files:
            try:
                result = self.import_file(
                    json_file=json_file,
                    update_existing=update_existing,
                    dry_run=dry_run,
                    chapter_code_override=chapter_code_override,
                    create_missing_branches=(
                        create_missing_branches
                    ),
                )

                stats[result["status"]] += 1
                stats["branches_created"] += result.get(
                    "branches_created",
                    0,
                )

            except Exception as exc:
                stats["errors"] += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"Erreur dans {json_file.name}: {exc}"
                    )
                )

                if stop_on_error:
                    raise CommandError(
                        f"Importation arrêtée : {exc}"
                    ) from exc

        self.display_summary(
            stats=stats,
            dry_run=dry_run,
        )

    def ensure_branches_relation_ready(self) -> None:
        """
        Vérifie que le modèle et la base de données sont prêts
        pour la relation ManyToMany ExerciseBac.branches.

        Cette méthode ne crée pas la table elle-même. La table
        doit être créée par les migrations Django.
        """
        try:
            branches_field = ExerciseBac._meta.get_field(
                "branches"
            )
        except Exception as exc:
            raise CommandError(
                "Le champ ExerciseBac.branches est introuvable. "
                "Ajoutez d'abord le ManyToManyField branches "
                "dans le modèle ExerciseBac."
            ) from exc

        if not getattr(
            branches_field,
            "many_to_many",
            False,
        ):
            raise CommandError(
                "ExerciseBac.branches doit être un "
                "ManyToManyField vers Branch."
            )

        through_model = branches_field.remote_field.through
        through_table = through_model._meta.db_table

        existing_tables = set(
            connection.introspection.table_names()
        )

        if through_table not in existing_tables:
            app_label = ExerciseBac._meta.app_label

            raise CommandError(
                "\nLa table intermédiaire ManyToMany "
                f"'{through_table}' n'existe pas dans la base.\n"
                "Ce problème ne vient pas du JSON ni du code "
                "d'ingestion : la migration qui crée "
                "ExerciseBac.branches n'a pas été appliquée.\n\n"
                "Exécutez :\n"
                f"  python manage.py makemigrations {app_label}\n"
                f"  python manage.py migrate {app_label}\n\n"
                "Puis vérifiez avec :\n"
                f"  python manage.py showmigrations {app_label}\n"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Relation ManyToMany prête : "
                f"{through_table}"
            )
        )

    def get_chapter(
        self,
        chapter_code: str,
    ) -> Chapter:
        normalized_code = chapter_code.strip().lower()

        try:
            return (
                Chapter.objects
                .select_related("subject")
                .get(code=normalized_code)
            )
        except Chapter.DoesNotExist as exc:
            raise CommandError(
                "Le chapitre avec le code "
                f"'{normalized_code}' est introuvable. "
                "Vérifiez Chapter.code dans la base et le "
                "champ chapter_code du JSON."
            ) from exc
        except Chapter.MultipleObjectsReturned as exc:
            raise CommandError(
                "Plusieurs chapitres utilisent le code "
                f"'{normalized_code}'. Chapter.code doit être "
                "unique pour permettre un ingest fiable."
            ) from exc

    def import_file(
        self,
        json_file: Path,
        update_existing: bool,
        dry_run: bool,
        chapter_code_override: str | None,
        create_missing_branches: bool,
    ) -> dict[str, Any]:
        data = self.read_json_file(
            json_file=json_file,
        )

        normalized_data = self.validate_and_normalize(
            data=data,
            filename=json_file.name,
        )

        code = normalized_data["code"]
        branch_specs = normalized_data["branches"]

        json_chapter_code = normalized_data["chapter_code"]
        selected_chapter_code = (
            chapter_code_override or json_chapter_code
        )

        chapter = self.get_chapter(
            chapter_code=selected_chapter_code,
        )

        if (
            chapter_code_override
            and chapter_code_override != json_chapter_code
        ):
            self.stdout.write(
                self.style.WARNING(
                    f"[OVERRIDE CHAPITRE] {json_file.name}: "
                    f"JSON={json_chapter_code} -> "
                    f"utilisé={chapter_code_override}"
                )
            )

        existing_exercise = (
            ExerciseBac.objects
            .filter(code=code)
            .first()
        )

        if existing_exercise and not update_existing:
            self.stdout.write(
                self.style.WARNING(
                    f"[IGNORÉ] {code} existe déjà. "
                    "Utilisez --update pour le modifier."
                )
            )

            return {
                "status": "skipped",
                "branches_created": 0,
            }

        if dry_run:
            missing_codes = self.get_missing_branch_codes(
                branch_specs=branch_specs,
            )

            if missing_codes and not create_missing_branches:
                raise ExerciseJSONValidationError(
                    "Filière(s) introuvable(s) : "
                    f"{', '.join(missing_codes)}. "
                    "Créez-les d'abord ou utilisez "
                    "--create-missing-branches."
                )

            branch_codes = [
                branch["code"]
                for branch in branch_specs
            ]

            suffix = ""
            if missing_codes:
                suffix = (
                    " — filière(s) à créer : "
                    f"{', '.join(missing_codes)}"
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"[VALIDÉ] {json_file.name} "
                    f"→ {code} "
                    f"→ chapitre {chapter.code} "
                    f"→ filières {', '.join(branch_codes)}"
                    f"{suffix}"
                )
            )

            return {
                "status": "validated",
                "branches_created": 0,
            }

        defaults = {
            "chapter": chapter,
            "year": normalized_data["year"],
            "exercise_number": (
                normalized_data["exercise_number"]
            ),
            "title": normalized_data["title"],
            "source_page": normalized_data["source_page"],
            "axis_tags": normalized_data["axis_tags"],
            "content": normalized_data["content"],
            "source_filename": json_file.name,
            "schema_version": (
                normalized_data["schema_version"]
            ),
            "language": normalized_data["language"],
            "direction": normalized_data["direction"],
            "is_active": normalized_data["is_active"],
        }

        with transaction.atomic():
            branches, branches_created = (
                self.resolve_branches(
                    branch_specs=branch_specs,
                    create_missing=(
                        create_missing_branches
                    ),
                )
            )

            exercise, created = (
                ExerciseBac.objects.update_or_create(
                    code=code,
                    defaults=defaults,
                )
            )

            # ManyToManyField doit être affecté après la sauvegarde.
            exercise.branches.set(branches)

        branch_codes = ", ".join(
            branch.code
            for branch in branches
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[CRÉÉ] {exercise.code} — "
                    f"{exercise.question_count} question(s) — "
                    f"chapitre : {chapter.code} — "
                    f"filières : {branch_codes}"
                )
            )

            return {
                "status": "created",
                "branches_created": branches_created,
            }

        self.stdout.write(
            self.style.SUCCESS(
                f"[MIS À JOUR] {exercise.code} — "
                f"{exercise.question_count} question(s) — "
                f"chapitre : {chapter.code} — "
                f"filières : {branch_codes}"
            )
        )

        return {
            "status": "updated",
            "branches_created": branches_created,
        }

    def resolve_branches(
        self,
        branch_specs: list[dict[str, str]],
        create_missing: bool,
    ) -> tuple[list[Branch], int]:
        """
        Retourne les objets Branch correspondant aux codes JSON.

        Avec create_missing=True, les filières absentes sont créées
        en utilisant leur nom dans le fichier JSON.
        """
        codes = [
            item["code"]
            for item in branch_specs
        ]

        existing = {
            branch.code: branch
            for branch in Branch.objects.filter(
                code__in=codes,
            )
        }

        missing_specs = [
            item
            for item in branch_specs
            if item["code"] not in existing
        ]

        if missing_specs and not create_missing:
            missing_codes = [
                item["code"]
                for item in missing_specs
            ]

            raise ExerciseJSONValidationError(
                "Filière(s) introuvable(s) : "
                f"{', '.join(missing_codes)}. "
                "Créez-les d'abord ou utilisez "
                "--create-missing-branches."
            )

        branches_created = 0

        for item in missing_specs:
            branch, created = Branch.objects.get_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                },
            )

            existing[item["code"]] = branch

            if created:
                branches_created += 1

        return [
            existing[code]
            for code in codes
        ], branches_created

    def get_missing_branch_codes(
        self,
        branch_specs: list[dict[str, str]],
    ) -> list[str]:
        codes = [
            item["code"]
            for item in branch_specs
        ]

        existing_codes = set(
            Branch.objects.filter(
                code__in=codes,
            ).values_list(
                "code",
                flat=True,
            )
        )

        return [
            code
            for code in codes
            if code not in existing_codes
        ]

    def read_json_file(
        self,
        json_file: Path,
    ) -> dict[str, Any]:
        try:
            raw_content = json_file.read_text(
                encoding="utf-8-sig",
            )
        except UnicodeDecodeError as exc:
            raise ExerciseJSONValidationError(
                "Le fichier n'est pas encodé correctement "
                "en UTF-8."
            ) from exc
        except OSError as exc:
            raise ExerciseJSONValidationError(
                f"Impossible de lire le fichier : {exc}"
            ) from exc

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ExerciseJSONValidationError(
                "JSON invalide à la ligne "
                f"{exc.lineno}, colonne {exc.colno}: "
                f"{exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise ExerciseJSONValidationError(
                "La racine du fichier JSON doit être un objet."
            )

        return data

    def validate_and_normalize(
        self,
        data: dict[str, Any],
        filename: str,
    ) -> dict[str, Any]:
        year = data.get("year")
        exercise_number = data.get(
            "exercise_number"
        )
        title = data.get("title")
        statement = data.get("statement")
        questions = data.get("questions")
        axis_tags = data.get(
            "axis_tags",
            [],
        )
        source_page = data.get(
            "source_page"
        )
        chapter_code = data.get("chapter_code")

        branch_specs = self.extract_branch_specs(
            data=data,
        )

        errors: list[str] = []

        if not isinstance(chapter_code, str) or not chapter_code.strip():
            errors.append(
                "chapter_code est obligatoire et doit être une chaîne non vide."
            )
        elif not re.fullmatch(
            r"[a-z0-9_-]+",
            chapter_code.strip().lower(),
        ):
            errors.append(
                "chapter_code invalide. Utilisez uniquement "
                "a-z, 0-9, _ ou -."
            )

        if not isinstance(year, int):
            errors.append(
                "year doit être un nombre entier."
            )
        elif year < 1962 or year > 2100:
            errors.append(
                "year contient une valeur invalide : "
                f"{year}."
            )

        if not isinstance(
            exercise_number,
            int,
        ):
            errors.append(
                "exercise_number doit être un nombre entier."
            )
        elif exercise_number < 1:
            errors.append(
                "exercise_number doit être supérieur "
                "ou égal à 1."
            )

        if not isinstance(
            title,
            str,
        ) or not title.strip():
            errors.append(
                "title est obligatoire."
            )

        if not isinstance(
            statement,
            str,
        ):
            errors.append(
                "statement doit être une chaîne "
                "de caractères."
            )
        elif not statement.strip():
            errors.append(
                "statement ne peut pas être vide."
            )

        if (
            source_page is not None
            and not isinstance(source_page, int)
        ):
            errors.append(
                "source_page doit être un nombre entier "
                "ou null."
            )

        if not branch_specs:
            errors.append(
                "Au moins une filière est obligatoire. "
                "Utilisez branch_codes, branches, "
                "branch_code ou branch."
            )

        if not isinstance(axis_tags, list):
            errors.append(
                "axis_tags doit être une liste."
            )
        else:
            for index, tag in enumerate(axis_tags):
                if not isinstance(
                    tag,
                    str,
                ) or not tag.strip():
                    errors.append(
                        f"axis_tags[{index}] doit être "
                        "une chaîne non vide."
                    )

        if not isinstance(questions, list):
            errors.append(
                "questions doit être une liste."
            )
        elif not questions:
            errors.append(
                "L'exercice doit contenir au moins "
                "une question."
            )
        else:
            errors.extend(
                self.validate_questions(
                    questions=questions,
                )
            )

        schema_version = str(
            data.get(
                "schema_version",
                data.get(
                    "version",
                    "1.0",
                ),
            )
        ).strip() or "1.0"

        if len(schema_version) > 30:
            errors.append(
                "schema_version ne peut pas dépasser "
                "30 caractères."
            )

        language = str(
            data.get(
                "language",
                "ar",
            )
        ).strip() or "ar"

        direction = str(
            data.get(
                "direction",
                "rtl",
            )
        ).strip() or "rtl"

        if len(language) > 10:
            errors.append(
                "language ne peut pas dépasser 10 caractères."
            )

        if len(direction) > 10:
            errors.append(
                "direction ne peut pas dépasser 10 caractères."
            )

        if errors:
            formatted_errors = "\n- ".join(errors)

            raise ExerciseJSONValidationError(
                f"Fichier {filename} invalide :\n"
                f"- {formatted_errors}"
            )

        normalized_chapter_code = chapter_code.strip().lower()

        normalized_axis_tags = self.normalize_string_list(
            values=axis_tags,
        )

        normalized_questions = (
            self.normalize_questions(
                questions=questions,
            )
        )

        code = self.normalize_code(
            value=data.get("code"),
            chapter_code=normalized_chapter_code,
            year=year,
            exercise_number=exercise_number,
            branch_codes=[
                item["code"]
                for item in branch_specs
            ],
        )

        canonical_branches = [
            {
                "code": item["code"],
                "name": item["name"],
            }
            for item in branch_specs
        ]

        normalized_content = dict(data)

        # Supprime les anciennes formes singulières pour éviter
        # d'avoir plusieurs sources de vérité dans content.
        normalized_content.pop("branch", None)
        normalized_content.pop("branch_code", None)

        normalized_content["code"] = code
        normalized_content["chapter_code"] = normalized_chapter_code
        normalized_content["branch_codes"] = [
            item["code"]
            for item in branch_specs
        ]
        normalized_content["branches"] = canonical_branches
        normalized_content["year"] = year
        normalized_content[
            "exercise_number"
        ] = exercise_number
        normalized_content["title"] = title.strip()
        normalized_content["statement"] = statement.strip()
        normalized_content["axis_tags"] = (
            normalized_axis_tags
        )
        normalized_content["questions"] = (
            normalized_questions
        )
        normalized_content["schema_version"] = (
            schema_version
        )
        normalized_content["language"] = language
        normalized_content["direction"] = direction

        return {
            "code": code,
            "chapter_code": normalized_chapter_code,
            "branches": canonical_branches,
            "year": year,
            "exercise_number": exercise_number,
            "title": title.strip(),
            "source_page": source_page,
            "axis_tags": normalized_axis_tags,
            "schema_version": schema_version,
            "language": language,
            "direction": direction,
            "is_active": bool(
                data.get(
                    "is_active",
                    True,
                )
            ),
            "content": normalized_content,
        }

    def extract_branch_specs(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, str]]:
        """
        Accepte les quatre formats suivants :

        1. "branch_codes": ["math", "science"]
        2. "branches": [
               {"code": "math", "name": "شعبة الرياضيات"},
               {"code": "science", "name": "شعبة علوم تجريبية"}
           ]
        3. "branch_code": "math"
        4. "branch": {"code": "math", "name": "شعبة الرياضيات"}

        Les données sont converties vers une liste canonique :
        [{"code": "...", "name": "..."}]
        """
        names_by_code: dict[str, str] = {}
        ordered_codes: list[str] = []

        def add_branch(
            raw_code: Any,
            raw_name: Any = None,
        ) -> None:
            if not isinstance(raw_code, str):
                return

            code = raw_code.strip().lower()

            if not code:
                return

            if not re.fullmatch(
                r"[a-z0-9_-]+",
                code,
            ):
                raise ExerciseJSONValidationError(
                    "Code de filière invalide : "
                    f"'{raw_code}'. Utilisez uniquement "
                    "a-z, 0-9, _ ou -."
                )

            name = ""
            if isinstance(raw_name, str):
                name = raw_name.strip()

            if code not in ordered_codes:
                ordered_codes.append(code)

            if name:
                names_by_code[code] = name
            elif code not in names_by_code:
                names_by_code[code] = (
                    self.default_branch_name(code)
                )

        branch_codes = data.get("branch_codes")

        if isinstance(branch_codes, list):
            for item in branch_codes:
                add_branch(item)

        branches = data.get("branches")

        if isinstance(branches, list):
            for item in branches:
                if isinstance(item, str):
                    add_branch(item)
                elif isinstance(item, dict):
                    add_branch(
                        item.get("code"),
                        item.get("name"),
                    )

        branch_code = data.get("branch_code")

        if isinstance(branch_code, str):
            add_branch(branch_code)

        branch = data.get("branch")

        if isinstance(branch, str):
            add_branch(branch)
        elif isinstance(branch, dict):
            add_branch(
                branch.get("code"),
                branch.get("name"),
            )

        return [
            {
                "code": code,
                "name": names_by_code[code],
            }
            for code in ordered_codes
        ]

    def default_branch_name(
        self,
        code: str,
    ) -> str:
        known_names = {
            "math": "شعبة الرياضيات",
            "science": "شعبة علوم تجريبية",
            "math_tech": "شعبة تقني رياضي",
            "gestion": "شعبة تسيير واقتصاد",
            "lettres": "شعبة آداب وفلسفة",
            "languages": "شعبة لغات أجنبية",
        }

        return known_names.get(
            code,
            code,
        )

    def normalize_code(
        self,
        value: Any,
        chapter_code: str,
        year: int,
        exercise_number: int,
        branch_codes: list[str],
    ) -> str:
        """
        Génère toujours un code canonique unique qui contient
        la/les filière(s), le chapitre, l'année et le numéro
        de l'exercice.

        Exemple :
        bac_science_electrical_phenomena_evolution_2008_exercise_03

        Le champ ``code`` éventuellement présent dans le JSON
        n'est volontairement pas réutilisé afin d'éviter de
        conserver un ancien format sans chapitre.
        """
        branch_part = "_".join(
            sorted(branch_codes)
        )

        normalized_chapter_code = (
            chapter_code.strip().lower()
        )

        code = (
            f"bac_{branch_part}_"
            f"{normalized_chapter_code}_"
            f"{year}_"
            f"exercise_{exercise_number:02d}"
        )

        if len(code) > 150:
            raise ExerciseJSONValidationError(
                "code ne peut pas dépasser 150 caractères. "
                f"Code généré : {code}"
            )

        return code

    def normalize_string_list(
        self,
        values: list[Any],
    ) -> list[str]:
        return list(
            dict.fromkeys(
                value.strip()
                for value in values
                if isinstance(value, str)
                and value.strip()
            )
        )

    def normalize_questions(
        self,
        questions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized_questions = []

        for question in questions:
            normalized_question = dict(question)

            normalized_question["id"] = (
                question["id"].strip()
            )

            normalized_question["text"] = (
                question["text"].strip()
            )

            question_axis_tags = question.get(
                "axis_tags",
                [],
            )

            normalized_question["axis_tags"] = (
                self.normalize_string_list(
                    values=question_axis_tags,
                )
            )

            solution = dict(
                question.get(
                    "solution",
                    {},
                )
            )

            if isinstance(
                solution.get("strategy"),
                str,
            ):
                solution["strategy"] = (
                    solution["strategy"].strip()
                )

            if isinstance(
                solution.get("final_answer"),
                str,
            ):
                solution["final_answer"] = (
                    solution["final_answer"].strip()
                )

            normalized_question["solution"] = solution

            normalized_questions.append(
                normalized_question
            )

        return normalized_questions

    def validate_questions(
        self,
        questions: list[Any],
    ) -> list[str]:
        errors: list[str] = []
        used_question_ids: set[str] = set()

        for index, question in enumerate(questions):
            location = f"questions[{index}]"

            if not isinstance(question, dict):
                errors.append(
                    f"{location} doit être un objet JSON."
                )
                continue

            question_id = question.get("id")
            question_text = question.get("text")
            solution_data = question.get("solution")

            if not isinstance(
                question_id,
                str,
            ) or not question_id.strip():
                errors.append(
                    f"{location}.id est obligatoire."
                )
            elif question_id.strip() in used_question_ids:
                errors.append(
                    f"{location}.id est dupliqué : "
                    f"{question_id.strip()}."
                )
            else:
                used_question_ids.add(
                    question_id.strip()
                )

            if not isinstance(
                question_text,
                str,
            ) or not question_text.strip():
                errors.append(
                    f"{location}.text est obligatoire."
                )

            question_axis_tags = question.get(
                "axis_tags",
                [],
            )

            if not isinstance(
                question_axis_tags,
                list,
            ):
                errors.append(
                    f"{location}.axis_tags doit être une liste."
                )
            else:
                for tag_index, tag in enumerate(
                    question_axis_tags
                ):
                    if not isinstance(
                        tag,
                        str,
                    ) or not tag.strip():
                        errors.append(
                            f"{location}.axis_tags"
                            f"[{tag_index}] doit être "
                            "une chaîne non vide."
                        )

            if not isinstance(
                solution_data,
                dict,
            ):
                errors.append(
                    f"{location}.solution doit être "
                    "un objet JSON."
                )
                continue

            strategy = solution_data.get("strategy")

            if (
                strategy is not None
                and not isinstance(strategy, str)
            ):
                errors.append(
                    f"{location}.solution.strategy "
                    "doit être une chaîne."
                )

            steps = solution_data.get("steps")

            if not isinstance(steps, list):
                errors.append(
                    f"{location}.solution.steps "
                    "doit être une liste."
                )
            else:
                errors.extend(
                    self.validate_solution_steps(
                        steps=steps,
                        question_location=location,
                    )
                )

            final_answer = solution_data.get(
                "final_answer"
            )

            if not isinstance(final_answer, str):
                errors.append(
                    f"{location}.solution.final_answer "
                    "doit être une chaîne."
                )

            graph_data = solution_data.get(
                "graph_data"
            )

            if (
                graph_data is not None
                and not isinstance(graph_data, dict)
            ):
                errors.append(
                    f"{location}.solution.graph_data "
                    "doit être un objet ou null."
                )

            table_data = solution_data.get(
                "table_data"
            )

            if (
                table_data is not None
                and not isinstance(
                    table_data,
                    (dict, list),
                )
            ):
                errors.append(
                    f"{location}.solution.table_data "
                    "doit être un objet, une liste ou null."
                )

            common_mistakes = solution_data.get(
                "common_mistakes",
                [],
            )

            if not isinstance(
                common_mistakes,
                list,
            ):
                errors.append(
                    f"{location}.solution.common_mistakes "
                    "doit être une liste."
                )

            hints = solution_data.get(
                "hints",
                [],
            )

            if not isinstance(hints, list):
                errors.append(
                    f"{location}.solution.hints "
                    "doit être une liste."
                )

        return errors

    def validate_solution_steps(
        self,
        steps: list[Any],
        question_location: str,
    ) -> list[str]:
        errors: list[str] = []

        for index, solution_step in enumerate(steps):
            location = (
                f"{question_location}."
                f"solution.steps[{index}]"
            )

            if not isinstance(
                solution_step,
                dict,
            ):
                errors.append(
                    f"{location} doit être un objet JSON."
                )
                continue

            step_number = solution_step.get(
                "step_number"
            )
            title = solution_step.get("title")
            explanation = solution_step.get(
                "explanation"
            )
            latex = solution_step.get("latex")

            if not isinstance(
                step_number,
                int,
            ):
                errors.append(
                    f"{location}.step_number "
                    "doit être un nombre entier."
                )

            if not isinstance(
                title,
                str,
            ) or not title.strip():
                errors.append(
                    f"{location}.title est obligatoire."
                )

            if not isinstance(
                explanation,
                str,
            ):
                errors.append(
                    f"{location}.explanation "
                    "doit être une chaîne."
                )

            if (
                latex is not None
                and not isinstance(latex, str)
            ):
                errors.append(
                    f"{location}.latex "
                    "doit être une chaîne ou null."
                )

        return errors

    def display_summary(
        self,
        stats: dict[str, int],
        dry_run: bool,
    ) -> None:
        self.stdout.write("")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Résumé de l'importation"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    "Fichiers validés : "
                    f"{stats['validated']}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Créés : {stats['created']}"
                )
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "Mis à jour : "
                    f"{stats['updated']}"
                )
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Ignorés : {stats['skipped']}"
                )
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "Filières créées : "
                    f"{stats['branches_created']}"
                )
            )

        if stats["errors"]:
            self.stdout.write(
                self.style.ERROR(
                    f"Erreurs : {stats['errors']}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Aucune erreur détectée."
                )
            )

