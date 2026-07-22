import json
from pathlib import Path
from typing import Any

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from course.models import Chapter
from exercise_bac.models import ExerciseBac


class ExerciseJSONValidationError(Exception):
    """
    Erreur levée lorsqu'un fichier JSON ne respecte pas
    la structure attendue.
    """


class Command(BaseCommand):
    help = (
        "Lit tous les fichiers JSON d'un dossier "
        "et insère les exercices dans ExerciseBac."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "folder",
            type=str,
            help=(
                "Chemin du dossier contenant "
                "les fichiers JSON."
            ),
        )

        parser.add_argument(
            "--update",
            action="store_true",
            help=(
                "Met à jour un exercice existant "
                "si son code existe déjà."
            ),
        )

        parser.add_argument(
            "--recursive",
            action="store_true",
            help=(
                "Recherche également les fichiers JSON "
                "dans les sous-dossiers."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Valide les fichiers sans écrire "
                "dans la base de données."
            ),
        )

        parser.add_argument(
            "--stop-on-error",
            action="store_true",
            help=(
                "Arrête complètement l'importation "
                "dès la première erreur."
            ),
        )

        parser.add_argument(
            "--chapter-code",
            type=str,
            default="sequences",
            help=(
                "Code du chapitre auquel rattacher "
                "les exercices. Valeur par défaut : sequences."
            ),
        )

    def handle(self, *args, **options):
        folder = Path(options["folder"]).resolve()

        update_existing = options["update"]
        recursive = options["recursive"]
        dry_run = options["dry_run"]
        stop_on_error = options["stop_on_error"]
        chapter_code = options["chapter_code"].strip()

        if not folder.exists():
            raise CommandError(
                f"Le dossier n'existe pas : {folder}"
            )

        if not folder.is_dir():
            raise CommandError(
                f"Le chemin n'est pas un dossier : {folder}"
            )

        if not chapter_code:
            raise CommandError(
                "Le code du chapitre ne peut pas être vide."
            )

        try:
            chapter = Chapter.objects.select_related(
                "subject",
            ).get(
                code=chapter_code,
            )
        except Chapter.DoesNotExist as exc:
            raise CommandError(
                f"Le chapitre avec le code "
                f"'{chapter_code}' est introuvable."
            ) from exc
        except Chapter.MultipleObjectsReturned as exc:
            raise CommandError(
                f"Plusieurs chapitres utilisent le code "
                f"'{chapter_code}'. Le code doit être unique."
            ) from exc

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
                f"Chapitre sélectionné : "
                f"{chapter.title} ({chapter.code})"
            )
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
        }

        for json_file in json_files:
            try:
                result = self.import_file(
                    json_file=json_file,
                    update_existing=update_existing,
                    dry_run=dry_run,
                    chapter=chapter,
                )

                stats[result] += 1

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

    def import_file(
        self,
        json_file: Path,
        update_existing: bool,
        dry_run: bool,
        chapter: Chapter,
    ) -> str:
        data = self.read_json_file(
            json_file=json_file,
        )

        normalized_data = self.validate_and_normalize(
            data=data,
            filename=json_file.name,
        )

        code = normalized_data["code"]

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[VALIDÉ] {json_file.name} "
                    f"→ {code} "
                    f"→ chapitre {chapter.code}"
                )
            )

            return "validated"

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

            return "skipped"

        defaults = {
            "chapter": chapter,
            "year": normalized_data["year"],
            "exercise_number": (
                normalized_data["exercise_number"]
            ),
            "title": normalized_data["title"],
            "source_page": (
                normalized_data["source_page"]
            ),
            "axis_tags": (
                normalized_data["axis_tags"]
            ),
            "content": normalized_data["content"],
            "source_filename": json_file.name,
            "schema_version": (
                normalized_data["schema_version"]
            ),
            "language": normalized_data["language"],
            "direction": normalized_data["direction"],
            "is_active": True,
        }

        with transaction.atomic():
            exercise, created = (
                ExerciseBac.objects.update_or_create(
                    code=code,
                    defaults=defaults,
                )
            )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[CRÉÉ] {exercise.code} — "
                    f"{exercise.question_count} question(s) — "
                    f"chapitre : {chapter.code}"
                )
            )

            return "created"

        self.stdout.write(
            self.style.SUCCESS(
                f"[MIS À JOUR] {exercise.code} — "
                f"{exercise.question_count} question(s) — "
                f"chapitre : {chapter.code}"
            )
        )

        return "updated"

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
                "Le fichier n'est pas encodé "
                "correctement en UTF-8."
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
                "La racine du fichier JSON "
                "doit être un objet."
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

        errors = []

        if not isinstance(year, int):
            errors.append(
                "year doit être un nombre entier."
            )
        elif year < 1962 or year > 2100:
            errors.append(
                f"year contient une valeur invalide : "
                f"{year}."
            )

        if not isinstance(
            exercise_number,
            int,
        ):
            errors.append(
                "exercise_number doit être "
                "un nombre entier."
            )
        elif exercise_number < 1:
            errors.append(
                "exercise_number doit être "
                "supérieur ou égal à 1."
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
                "source_page doit être un nombre "
                "entier ou null."
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
                "L'exercice doit contenir "
                "au moins une question."
            )
        else:
            question_errors = (
                self.validate_questions(
                    questions=questions,
                )
            )

            errors.extend(question_errors)

        if errors:
            formatted_errors = "\n- ".join(
                errors
            )

            raise ExerciseJSONValidationError(
                f"Fichier {filename} invalide :\n"
                f"- {formatted_errors}"
            )

        code = data.get("code")

        if not isinstance(code, str) or not code.strip():
            code = (
                f"bac_{year}_"
                f"exercise_{exercise_number:02d}"
            )
        else:
            code = code.strip()

        normalized_axis_tags = list(
            dict.fromkeys(
                tag.strip()
                for tag in axis_tags
                if isinstance(tag, str)
                and tag.strip()
            )
        )

        normalized_questions = (
            self.normalize_questions(
                questions=questions,
            )
        )

        normalized_content = dict(data)

        normalized_content["code"] = code
        normalized_content["year"] = year
        normalized_content[
            "exercise_number"
        ] = exercise_number
        normalized_content["title"] = (
            title.strip()
        )
        normalized_content["statement"] = (
            statement.strip()
        )
        normalized_content["axis_tags"] = (
            normalized_axis_tags
        )
        normalized_content["questions"] = (
            normalized_questions
        )

        return {
            "code": code,
            "year": year,
            "exercise_number": (
                exercise_number
            ),
            "title": title.strip(),
            "source_page": source_page,
            "axis_tags": (
                normalized_axis_tags
            ),
            "schema_version": str(
                data.get(
                    "schema_version",
                    "1.0",
                )
            ),
            "language": str(
                data.get(
                    "language",
                    "ar",
                )
            ),
            "direction": str(
                data.get(
                    "direction",
                    "rtl",
                )
            ),
            "content": normalized_content,
        }

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

            normalized_question["axis_tags"] = list(
                dict.fromkeys(
                    tag.strip()
                    for tag in question_axis_tags
                    if isinstance(tag, str)
                    and tag.strip()
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
                    solution[
                        "final_answer"
                    ].strip()
                )

            normalized_question["solution"] = (
                solution
            )

            normalized_questions.append(
                normalized_question
            )

        return normalized_questions

    def validate_questions(
        self,
        questions: list[Any],
    ) -> list[str]:
        errors = []
        used_question_ids = set()

        for index, question in enumerate(
            questions
        ):
            location = f"questions[{index}]"

            if not isinstance(question, dict):
                errors.append(
                    f"{location} doit être "
                    "un objet JSON."
                )
                continue

            question_id = question.get("id")
            question_text = question.get(
                "text"
            )
            solution = question.get(
                "solution"
            )

            if not isinstance(
                question_id,
                str,
            ) or not question_id.strip():
                errors.append(
                    f"{location}.id est obligatoire."
                )
            elif (
                question_id.strip()
                in used_question_ids
            ):
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

            question_axis_tags = (
                question.get(
                    "axis_tags",
                    [],
                )
            )

            if not isinstance(
                question_axis_tags,
                list,
            ):
                errors.append(
                    f"{location}.axis_tags "
                    "doit être une liste."
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
                solution,
                dict,
            ):
                errors.append(
                    f"{location}.solution "
                    "doit être un objet JSON."
                )
                continue

            strategy = solution.get(
                "strategy"
            )

            if (
                strategy is not None
                and not isinstance(
                    strategy,
                    str,
                )
            ):
                errors.append(
                    f"{location}.solution.strategy "
                    "doit être une chaîne."
                )

            steps = solution.get("steps")

            if not isinstance(steps, list):
                errors.append(
                    f"{location}.solution.steps "
                    "doit être une liste."
                )
            else:
                step_errors = (
                    self.validate_solution_steps(
                        steps=steps,
                        question_location=location,
                    )
                )

                errors.extend(step_errors)

            final_answer = solution.get(
                "final_answer"
            )

            if not isinstance(
                final_answer,
                str,
            ):
                errors.append(
                    f"{location}.solution."
                    "final_answer doit être "
                    "une chaîne."
                )

            graph_data = solution.get(
                "graph_data"
            )

            if (
                graph_data is not None
                and not isinstance(
                    graph_data,
                    dict,
                )
            ):
                errors.append(
                    f"{location}.solution."
                    "graph_data doit être "
                    "un objet ou null."
                )

            table_data = solution.get(
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
                    f"{location}.solution."
                    "table_data doit être "
                    "un objet, une liste ou null."
                )

            common_mistakes = solution.get(
                "common_mistakes",
                [],
            )

            if not isinstance(
                common_mistakes,
                list,
            ):
                errors.append(
                    f"{location}.solution."
                    "common_mistakes doit être "
                    "une liste."
                )

            hints = solution.get(
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
        errors = []

        for index, solution_step in enumerate(
            steps
        ):
            location = (
                f"{question_location}."
                f"solution.steps[{index}]"
            )

            if not isinstance(
                solution_step,
                dict,
            ):
                errors.append(
                    f"{location} doit être "
                    "un objet JSON."
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
                    f"{location}.title "
                    "est obligatoire."
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
                and not isinstance(
                    latex,
                    str,
                )
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
    ):
        self.stdout.write("")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Résumé de l'importation"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Fichiers validés : "
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
                    f"Mis à jour : "
                    f"{stats['updated']}"
                )
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Ignorés : {stats['skipped']}"
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