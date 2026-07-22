import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from course.models import (
    Axis,
    Branch,
    Chapter,
    Question,
    Subject,
)


class Command(BaseCommand):
    """
    Importe un fichier JSON contenant des questions de cours
    ou de baccalauréat.

    La solution et le graphe sont stockés directement dans :

        Question.solution
        Question.graph_data

    Les champs solution et graph_data sont des JSONField.
    Leur structure reste libre.

    Structure générale acceptée :

    {
        "version": 3,
        "language": "ar",
        "direction": "rtl",
        "subject_code": "math",
        "chapter_code": "numerical_sequences",
        "tag": "seq_monotonicity",
        "title": "اتجاه تغير المتتالية",
        "source_file": "...",
        "years": [2008, 2010],
        "questions": [
            {
                "id": "bac_2008_question_1",
                "year": 2008,
                "text": "...",
                "standalone_text": "...",
                "context": "...",
                "standalone_support": [],
                "solution": {
                    "strategy": "...",
                    "simple_solution": {},
                    "steps": [],
                    "final_answer": "..."
                },
                "graph_data": {
                    "graph_type": "cobweb",
                    "react_data": {
                        "axes": {},
                        "series": []
                    }
                }
            }
        ]
    }
    """

    help = (
        "Importe des questions JSON et stocke directement "
        "la solution dans Question.solution et le graphe "
        "dans Question.graph_data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help=(
                "Chemin vers un fichier JSON ou vers un dossier "
                "contenant plusieurs fichiers JSON."
            ),
        )

        parser.add_argument(
            "--subject-name",
            type=str,
            default="الرياضيات",
            help="Nom de la matière si elle doit être créée.",
        )

        parser.add_argument(
            "--chapter-title",
            type=str,
            default="المتتاليات العددية",
            help="Titre du chapitre si celui-ci doit être créé.",
        )

        parser.add_argument(
            "--branch-code",
            type=str,
            default=None,
            help=(
                "Code de la filière par défaut. "
                "Exemple : science."
            ),
        )

        parser.add_argument(
            "--branch-name",
            type=str,
            default=None,
            help=(
                "Nom de la filière si elle doit être créée. "
                "Utilisé avec --branch-code."
            ),
        )

        parser.add_argument(
            "--replace",
            action="store_true",
            help=(
                "Supprime toutes les anciennes questions de l'axe "
                "avant l'import."
            ),
        )

        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Désactive les questions absentes du fichier JSON."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Teste l'import sans enregistrer les modifications."
            ),
        )

    def handle(self, *args, **options):
        input_path = Path(
            options["file"]
        ).expanduser().resolve()

        if not input_path.exists():
            raise CommandError(
                f"Chemin introuvable : {input_path}"
            )

        json_files = self.get_json_files(
            input_path
        )

        if not json_files:
            raise CommandError(
                f"Aucun fichier JSON trouvé dans : {input_path}"
            )

        totals = {
            "files": 0,
            "subjects_created": 0,
            "chapters_created": 0,
            "branches_created": 0,
            "questions_created": 0,
            "questions_updated": 0,
            "questions_with_solution": 0,
            "questions_without_solution": 0,
            "questions_with_graph": 0,
            "questions_without_graph": 0,
            "questions_deactivated": 0,
            "errors": 0,
        }

        try:
            with transaction.atomic():
                for json_file in json_files:
                    file_totals = self.import_file(
                        json_file=json_file,
                        options=options,
                    )

                    totals["files"] += 1

                    for key, value in file_totals.items():
                        if key in totals:
                            totals[key] += value

                if options["dry_run"]:
                    transaction.set_rollback(
                        True
                    )

        except Exception as exc:
            raise CommandError(
                f"Échec de l'import : {exc}"
            ) from exc

        self.print_summary(
            totals=totals,
            dry_run=options["dry_run"],
        )

    def get_json_files(
        self,
        input_path: Path,
    ) -> list[Path]:
        """
        Accepte un fichier JSON ou un dossier complet.
        """

        if input_path.is_file():
            if input_path.suffix.lower() != ".json":
                raise CommandError(
                    "Le fichier doit avoir l'extension .json."
                )

            return [input_path]

        return sorted(
            file_path
            for file_path in input_path.rglob("*.json")
            if file_path.is_file()
        )

    def load_json(
        self,
        json_path: Path,
    ) -> dict:
        """
        Charge un fichier JSON encodé en UTF-8.
        """

        try:
            with json_path.open(
                mode="r",
                encoding="utf-8-sig",
            ) as file:
                data = json.load(
                    file
                )

        except UnicodeDecodeError as exc:
            raise CommandError(
                f"{json_path.name} doit être encodé en UTF-8."
            ) from exc

        except json.JSONDecodeError as exc:
            raise CommandError(
                f"JSON invalide dans {json_path.name}, "
                f"ligne {exc.lineno}, colonne {exc.colno} : "
                f"{exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise CommandError(
                f"La racine de {json_path.name} "
                "doit être un objet JSON."
            )

        return data

    def import_file(
        self,
        json_file: Path,
        options: dict,
    ) -> dict:
        root = self.load_json(
            json_file
        )

        self.validate_root(
            root=root,
            json_file=json_file,
        )

        questions = root["questions"]

        file_totals = {
            "subjects_created": 0,
            "chapters_created": 0,
            "branches_created": 0,
            "questions_created": 0,
            "questions_updated": 0,
            "questions_with_solution": 0,
            "questions_without_solution": 0,
            "questions_with_graph": 0,
            "questions_without_graph": 0,
            "questions_deactivated": 0,
            "errors": 0,
        }

        subject, subject_created = (
            self.get_or_create_subject(
                root=root,
                options=options,
            )
        )

        if subject_created:
            file_totals[
                "subjects_created"
            ] += 1

        chapter, chapter_created = (
            self.get_or_create_chapter(
                root=root,
                options=options,
                subject=subject,
            )
        )

        if chapter_created:
            file_totals[
                "chapters_created"
            ] += 1

        axis = self.get_existing_axis(
            root=root,
        )

        default_branch, branch_created = (
            self.get_or_create_branch(
                branch_code=options.get(
                    "branch_code"
                ),
                branch_name=options.get(
                    "branch_name"
                ),
            )
        )

        if branch_created:
            file_totals[
                "branches_created"
            ] += 1

        if options["replace"]:
            deleted_count, _ = (
                Question.objects.filter(
                    axis=axis,
                ).delete()
            )

            self.stdout.write(
                self.style.WARNING(
                    f"{json_file.name} : "
                    f"{deleted_count} ancienne(s) entrée(s) supprimée(s)."
                )
            )

        imported_codes: set[str] = set()

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Import : {json_file.name}"
            )
        )

        self.stdout.write(
            f"Matière  : {subject.code} - {subject.name}"
        )

        self.stdout.write(
            f"Chapitre : {chapter.code} - {chapter.title}"
        )

        self.stdout.write(
            f"Axe      : {axis.tag} - {axis.title}"
        )

        self.stdout.write(
            f"Questions: {len(questions)}"
        )

        for position, raw_question in enumerate(
            questions,
            start=1,
        ):
            try:
                normalized = self.normalize_question(
                    raw_question=raw_question,
                    root=root,
                    json_file=json_file,
                    position=position,
                    default_branch=default_branch,
                )

                question_code = normalized.pop(
                    "code"
                )

                imported_codes.add(
                    question_code
                )

                question, question_created = (
                    Question.objects.update_or_create(
                        axis=axis,
                        code=question_code,
                        defaults=normalized,
                    )
                )

                question.full_clean()
                question.save()

                if question_created:
                    file_totals[
                        "questions_created"
                    ] += 1

                    question_status = "créée"
                else:
                    file_totals[
                        "questions_updated"
                    ] += 1

                    question_status = "mise à jour"

                if self.has_solution(
                    question.solution
                ):
                    file_totals[
                        "questions_with_solution"
                    ] += 1

                    solution_status = "avec solution JSON"
                else:
                    file_totals[
                        "questions_without_solution"
                    ] += 1

                    solution_status = "sans solution"

                if self.has_graph(
                    question.graph_data
                ):
                    file_totals[
                        "questions_with_graph"
                    ] += 1

                    graph_status = "avec graphe JSON"
                else:
                    file_totals[
                        "questions_without_graph"
                    ] += 1

                    graph_status = "sans graphe"

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {question_code} : "
                        f"question {question_status}, "
                        f"{solution_status}, "
                        f"{graph_status}"
                    )
                )

            except Exception as exc:
                file_totals[
                    "errors"
                ] += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"  ✗ Question {position} : {exc}"
                    )
                )

        if options["deactivate_missing"]:
            missing_questions = (
                Question.objects.filter(
                    axis=axis,
                    is_active=True,
                )
            )

            if imported_codes:
                missing_questions = (
                    missing_questions.exclude(
                        code__in=imported_codes,
                    )
                )

            deactivated_count = (
                missing_questions.update(
                    is_active=False,
                )
            )

            file_totals[
                "questions_deactivated"
            ] += deactivated_count

        self.update_axis_content(
            axis=axis,
            root=root,
        )

        return file_totals

    def validate_root(
        self,
        root: dict,
        json_file: Path,
    ):
        """
        Vérifie les propriétés obligatoires du fichier.
        """

        required_fields = [
            "subject_code",
            "chapter_code",
            "tag",
            "title",
            "questions",
        ]

        missing_fields = [
            field_name
            for field_name in required_fields
            if field_name not in root
        ]

        if missing_fields:
            raise CommandError(
                f"{json_file.name} ne contient pas : "
                f"{', '.join(missing_fields)}"
            )

        if not isinstance(
            root["questions"],
            list,
        ):
            raise CommandError(
                f"{json_file.name} : "
                "questions doit être une liste."
            )

        string_fields = [
            "subject_code",
            "chapter_code",
            "tag",
            "title",
        ]

        for field_name in string_fields:
            if not self.clean_string(
                root.get(field_name)
            ):
                raise CommandError(
                    f"{json_file.name} : "
                    f"{field_name} est vide."
                )

    def get_or_create_subject(
        self,
        root: dict,
        options: dict,
    ) -> tuple[Subject, bool]:
        subject_code = self.clean_string(
            root["subject_code"]
        )

        subject_name = self.clean_string(
            root.get("subject_name")
            or options["subject_name"]
        )

        subject, created = (
            Subject.objects.get_or_create(
                code=subject_code,
                defaults={
                    "name": subject_name,
                    "description": "",
                },
            )
        )

        changed_fields = []

        if not created:
            if (
                subject_name
                and subject.name != subject_name
            ):
                subject.name = subject_name
                changed_fields.append(
                    "name"
                )

            if changed_fields:
                subject.save(
                    update_fields=changed_fields
                )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Matière créée : {subject.code}"
                )
            )

        return subject, created

    def get_or_create_chapter(
        self,
        root: dict,
        options: dict,
        subject: Subject,
    ) -> tuple[Chapter, bool]:
        chapter_code = self.clean_string(
            root["chapter_code"]
        )

        chapter_title = self.clean_string(
            root.get("chapter_title")
            or options["chapter_title"]
        )

        chapter, created = (
            Chapter.objects.get_or_create(
                subject=subject,
                code=chapter_code,
                defaults={
                    "title": chapter_title,
                    "order": 1,
                    "is_active": True,
                },
            )
        )

        changed_fields = []

        if not created:
            if (
                chapter_title
                and chapter.title != chapter_title
            ):
                chapter.title = chapter_title

                changed_fields.append(
                    "title"
                )

            if not chapter.is_active:
                chapter.is_active = True

                changed_fields.append(
                    "is_active"
                )

            if changed_fields:
                chapter.save(
                    update_fields=changed_fields
                )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Chapitre créé : {chapter.code}"
                )
            )

        return chapter, created

    def get_existing_axis(
        self,
        root: dict,
    ) -> Axis:
        """
        Recherche un axe existant avec son tag.

        Aucun axe n'est créé automatiquement.
        """

        axis_tag = self.clean_string(
            root["tag"]
        )

        queryset = (
            Axis.objects
            .select_related(
                "chapter",
                "chapter__subject",
            )
            .filter(
                tag=axis_tag,
            )
        )

        axis_count = queryset.count()

        if axis_count == 0:
            available_tags = list(
                Axis.objects
                .order_by("tag")
                .values_list(
                    "tag",
                    flat=True,
                )
            )

            available_message = (
                ", ".join(available_tags)
                if available_tags
                else "aucun axe"
            )

            raise CommandError(
                f"Axe introuvable avec le tag "
                f"'{axis_tag}'. "
                f"Axes disponibles : "
                f"{available_message}."
            )

        if axis_count > 1:
            matching_axes = list(
                queryset.values_list(
                    "id",
                    "chapter__code",
                    "title",
                )
            )

            details = "; ".join(
                (
                    f"id={axis_id}, "
                    f"chapitre={chapter_code}, "
                    f"titre={title}"
                )
                for (
                    axis_id,
                    chapter_code,
                    title,
                ) in matching_axes
            )

            raise CommandError(
                f"Plusieurs axes possèdent "
                f"le tag '{axis_tag}'. "
                f"Résultats : {details}"
            )

        axis = queryset.first()

        if not axis.is_active:
            raise CommandError(
                f"L'axe '{axis_tag}' existe "
                "mais il est désactivé."
            )

        return axis

    def get_or_create_branch(
        self,
        branch_code: str | None,
        branch_name: str | None,
    ) -> tuple[Branch | None, bool]:
        """
        Retourne la filière par défaut.

        Si aucun code n'est fourni, retourne :
        (None, False)
        """

        if not branch_code:
            return None, False

        normalized_code = self.clean_string(
            branch_code
        )

        normalized_name = self.clean_string(
            branch_name
            or normalized_code
        )

        branch, created = (
            Branch.objects.get_or_create(
                code=normalized_code,
                defaults={
                    "name": normalized_name,
                },
            )
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Filière créée : {branch.code}"
                )
            )

        return branch, created

    def normalize_question(
        self,
        raw_question: Any,
        root: dict,
        json_file: Path,
        position: int,
        default_branch: Branch | None,
    ) -> dict:
        """
        Convertit une question JSON en données compatibles
        avec le modèle Question.
        """

        if not isinstance(
            raw_question,
            dict,
        ):
            raise ValueError(
                "La question doit être un objet JSON."
            )

        code = self.clean_string(
            raw_question.get("id")
            or raw_question.get("code")
        )

        if not code:
            raise ValueError(
                "Le champ id ou code est obligatoire."
            )

        text = self.clean_string(
            raw_question.get("text")
            or raw_question.get("question")
        )

        if not text:
            raise ValueError(
                f"Le texte de la question "
                f"'{code}' est vide."
            )

        root_tag = self.clean_string(
            root.get("tag")
        )

        question_tag = self.clean_string(
            raw_question.get("tag")
        )

        if (
            question_tag
            and root_tag
            and question_tag != root_tag
        ):
            raise ValueError(
                f"Tag incorrect pour '{code}' : "
                f"{question_tag} != {root_tag}"
            )

        context = self.clean_string(
            raw_question.get("context")
        )

        standalone_text = self.clean_string(
            raw_question.get(
                "standalone_text"
            )
        )

        if not standalone_text:
            standalone_text = self.build_standalone_text(
                context=context,
                text=text,
            )

        original_text = self.clean_string(
            raw_question.get("original_text")
            or raw_question.get("original_question")
            or text
        )

        standalone_support = self.ensure_list(
            raw_question.get(
                "standalone_support"
            )
        )

        secondary_tags = self.ensure_list(
            raw_question.get(
                "secondary_tags"
            )
        )

        depends_on = self.ensure_list(
            raw_question.get(
                "depends_on"
            )
        )

        images = self.ensure_list(
            raw_question.get(
                "images"
            )
        )

        solution = self.normalize_solution_json(
            solution_data=raw_question.get(
                "solution"
            ),
            question_code=code,
        )

        graph_data = self.normalize_graph_json(
            graph_data=raw_question.get(
                "graph_data"
            ),
            question_code=code,
        )

        metadata = raw_question.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        metadata = {
            **metadata,
            "axis_title": raw_question.get(
                "axis",
                root.get("title", ""),
            ),
            "original_text_note": raw_question.get(
                "original_text_note",
                "",
            ),
            "source_numbers": self.ensure_list(
                raw_question.get(
                    "source_numbers"
                )
            ),
            "imported_from": json_file.name,
            "json_version": root.get(
                "version",
                1,
            ),
            "language": root.get(
                "language",
                "ar",
            ),
            "direction": root.get(
                "direction",
                "rtl",
            ),
        }

        is_standalone = self.normalize_boolean(
            raw_question.get(
                "is_standalone"
            ),
            default=True,
        )

        return {
            "code": code,

            "branch": self.resolve_question_branch(
                raw_question=raw_question,
                default_branch=default_branch,
            ),

            "number": self.clean_string(
                raw_question.get(
                    "number"
                )
            ),

            "exercise": self.clean_string(
                raw_question.get(
                    "exercise"
                )
            ),

            "title": self.clean_string(
                raw_question.get("title")
                or raw_question.get("skill")
            ),

            "text": text,

            "standalone_text": standalone_text,

            "context": context,

            "standalone_support": (
                standalone_support
            ),

            "original_text": original_text,

            "question_type": (
                self.normalize_question_type(
                    raw_question.get(
                        "question_type"
                    )
                    or raw_question.get(
                        "type"
                    )
                    or "bac"
                )
            ),

            "difficulty": (
                self.normalize_difficulty(
                    raw_question.get(
                        "difficulty"
                    )
                )
            ),

            "skill": self.clean_string(
                raw_question.get(
                    "skill"
                )
            ),

            "year": self.optional_positive_integer(
                raw_question.get(
                    "year"
                ),
                field_name="year",
            ),

            "source_file": self.clean_string(
                raw_question.get(
                    "source_file"
                )
                or root.get(
                    "source_file"
                )
                or json_file.name
            ),

            "source_page": (
                self.optional_positive_integer(
                    raw_question.get(
                        "source_page"
                    ),
                    field_name="source_page",
                )
            ),

            "secondary_tags": secondary_tags,

            "depends_on": depends_on,

            "images": images,

            "solution": solution,

            "graph_data": graph_data,

            "metadata": metadata,

            "is_standalone": is_standalone,

            "is_active": self.normalize_boolean(
                raw_question.get(
                    "is_active"
                ),
                default=True,
            ),

            "order": (
                self.optional_positive_integer(
                    raw_question.get(
                        "order"
                    ),
                    field_name="order",
                )
                or position
            ),
        }

    def normalize_solution_json(
        self,
        solution_data: Any,
        question_code: str,
    ) -> dict:
        """
        Conserve toute la structure de la solution.

        Aucun champ interne n'est supprimé.

        Cela permet d'accepter :

        - simple_solution
        - strategy
        - detailed_explanation
        - steps
        - bac_writing
        - algorithm
        - final_answer_box
        - understanding_check
        - graph
        - toute nouvelle propriété future
        """

        if solution_data in (
            None,
            "",
        ):
            return {}

        if isinstance(
            solution_data,
            str,
        ):
            cleaned_solution = (
                solution_data.strip()
            )

            return {
                "simple_solution": {
                    "explanation": cleaned_solution,
                    "final_answer": cleaned_solution,
                },
                "detailed_explanation": (
                    cleaned_solution
                ),
                "final_answer": (
                    cleaned_solution
                ),
                "is_complete": True,
            }

        if not isinstance(
            solution_data,
            dict,
        ):
            raise ValueError(
                f"La solution de '{question_code}' "
                "doit être un objet JSON."
            )

        normalized_solution = (
            self.deep_copy_json_value(
                solution_data
            )
        )

        if "steps" in normalized_solution:
            steps = normalized_solution[
                "steps"
            ]

            if steps is None:
                normalized_solution[
                    "steps"
                ] = []

            elif not isinstance(
                steps,
                list,
            ):
                normalized_solution[
                    "steps"
                ] = [steps]

        if "hints" in normalized_solution:
            normalized_solution[
                "hints"
            ] = self.ensure_list(
                normalized_solution.get(
                    "hints"
                )
            )

        if "common_mistakes" in normalized_solution:
            normalized_solution[
                "common_mistakes"
            ] = self.ensure_list(
                normalized_solution.get(
                    "common_mistakes"
                )
            )

        if "bac_writing" in normalized_solution:
            normalized_solution[
                "bac_writing"
            ] = self.ensure_list(
                normalized_solution.get(
                    "bac_writing"
                )
            )

        if (
            "understanding_check"
            in normalized_solution
        ):
            normalized_solution[
                "understanding_check"
            ] = self.ensure_list(
                normalized_solution.get(
                    "understanding_check"
                )
            )

        if "is_complete" not in normalized_solution:
            normalized_solution[
                "is_complete"
            ] = True

        return normalized_solution

    def normalize_graph_json(
        self,
        graph_data: Any,
        question_code: str,
    ) -> dict:
        """
        Conserve toute la structure de graph_data.

        Le graphe est enregistré directement dans :

            Question.graph_data

        Valeurs acceptées :

        - objet JSON non vide ;
        - objet JSON vide {} ;
        - null ou chaîne vide, convertis en {}.

        Les listes ou chaînes non vides sont refusées afin de
        respecter le modèle JSONField attendu par le frontend.
        """

        if graph_data in (
            None,
            "",
        ):
            return {}

        if not isinstance(
            graph_data,
            dict,
        ):
            raise ValueError(
                f"Le graphe de '{question_code}' "
                "doit être un objet JSON."
            )

        return self.deep_copy_json_value(
            graph_data
        )

    def resolve_question_branch(
        self,
        raw_question: dict,
        default_branch: Branch | None,
    ) -> Branch | None:
        branch_value = (
            raw_question.get(
                "branch_code"
            )
            or raw_question.get(
                "branch"
            )
        )

        if not branch_value:
            return default_branch

        if isinstance(
            branch_value,
            dict,
        ):
            branch_code = self.clean_string(
                branch_value.get(
                    "code"
                )
            )

            branch_name = self.clean_string(
                branch_value.get(
                    "name"
                )
                or branch_code
            )
        else:
            branch_code = self.clean_string(
                branch_value
            )

            branch_name = branch_code

        if not branch_code:
            return default_branch

        branch = (
            Branch.objects.filter(
                code__iexact=branch_code,
            ).first()
            or Branch.objects.filter(
                name__iexact=branch_name,
            ).first()
        )

        if branch:
            return branch

        return Branch.objects.create(
            code=branch_code,
            name=branch_name,
        )

    def update_axis_content(
        self,
        axis: Axis,
        root: dict,
    ):
        current_content = (
            axis.content
            if isinstance(
                axis.content,
                dict,
            )
            else {}
        )

        axis.content = self.deep_merge(
            current_content,
            self.build_axis_content(
                root
            ),
        )

        axis.save(
            update_fields=[
                "content",
            ]
        )

    def build_axis_content(
        self,
        root: dict,
    ) -> dict:
        """
        Enregistre uniquement les métadonnées générales
        du fichier dans Axis.content.
        """

        return {
            "version": root.get(
                "version",
                1,
            ),
            "language": root.get(
                "language",
                "ar",
            ),
            "direction": root.get(
                "direction",
                "rtl",
            ),
            "subject_code": root.get(
                "subject_code",
                "",
            ),
            "chapter_code": root.get(
                "chapter_code",
                "",
            ),
            "axis_tag": root.get(
                "tag",
                "",
            ),
            "axis_title": root.get(
                "title",
                "",
            ),
            "source_file": root.get(
                "source_file",
                "",
            ),
            "question_count": len(
                root.get(
                    "questions",
                    []
                )
            ),
            "years": self.ensure_list(
                root.get(
                    "years"
                )
            ),
            "solution_schema": root.get(
                "solution_schema",
                {},
            ),
        }

    def build_standalone_text(
        self,
        context: str,
        text: str,
    ) -> str:
        """
        Construit automatiquement un énoncé autonome.
        """

        parts = []

        if context:
            parts.append(
                context.strip()
            )

        if text:
            parts.append(
                text.strip()
            )

        return "\n\n".join(
            parts
        )

    def has_solution(
        self,
        solution: Any,
    ) -> bool:
        return bool(
            isinstance(
                solution,
                dict,
            )
            and solution
        )

    def has_graph(
        self,
        graph_data: Any,
    ) -> bool:
        return bool(
            isinstance(
                graph_data,
                dict,
            )
            and graph_data
        )

    def normalize_question_type(
        self,
        value: Any,
    ) -> str:
        normalized = self.clean_string(
            value
        ).lower()

        aliases = {
            "bac_question": "bac",
            "exercise": "practice",
            "exercice": "practice",
            "guided_exercise": "guided",
            "تمرين بكالوريا": "bac",
            "تمرين موجه": "guided",
            "تمرين تطبيقي": "practice",
            "اختبار": "quiz",
            "اختبار قصير": "quiz",
        }

        normalized = aliases.get(
            normalized,
            normalized,
        )

        allowed_values = {
            "bac",
            "guided",
            "practice",
            "quiz",
        }

        if normalized not in allowed_values:
            return "bac"

        return normalized

    def normalize_difficulty(
        self,
        value: Any,
    ) -> str:
        normalized = self.clean_string(
            value
            or "medium"
        ).lower()

        aliases = {
            "1": "easy",
            "2": "medium",
            "3": "hard",
            "easy": "easy",
            "facile": "easy",
            "سهل": "easy",
            "medium": "medium",
            "moyen": "medium",
            "متوسط": "medium",
            "hard": "hard",
            "difficile": "hard",
            "صعب": "hard",
        }

        return aliases.get(
            normalized,
            "medium",
        )

    def normalize_boolean(
        self,
        value: Any,
        default: bool,
    ) -> bool:
        if value is None:
            return default

        if isinstance(
            value,
            bool,
        ):
            return value

        normalized = self.clean_string(
            value
        ).lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "oui",
            "نعم",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "non",
            "لا",
        }:
            return False

        return default

    def optional_positive_integer(
        self,
        value: Any,
        field_name: str,
    ) -> int | None:
        if value in (
            None,
            "",
        ):
            return None

        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{field_name} doit être un entier."
            )

        try:
            result = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} doit être un entier."
            ) from exc

        if result < 0:
            raise ValueError(
                f"{field_name} ne peut pas être négatif."
            )

        return result

    def ensure_list(
        self,
        value: Any,
    ) -> list:
        if value in (
            None,
            "",
        ):
            return []

        if isinstance(
            value,
            list,
        ):
            return value

        return [value]

    def clean_string(
        self,
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(
            value
        ).strip()

    def deep_copy_json_value(
        self,
        value: Any,
    ) -> Any:
        """
        Crée une copie JSON sûre.

        Cela vérifie aussi que le contenu est sérialisable.
        """

        try:
            return json.loads(
                json.dumps(
                    value,
                    ensure_ascii=False,
                )
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "La donnée contient une valeur "
                "qui n'est pas compatible avec JSON."
            ) from exc

    def deep_merge(
        self,
        old_data: dict,
        new_data: dict,
    ) -> dict:
        result = old_data.copy()

        for key, new_value in new_data.items():
            old_value = result.get(
                key
            )

            if (
                isinstance(
                    old_value,
                    dict,
                )
                and isinstance(
                    new_value,
                    dict,
                )
            ):
                result[key] = self.deep_merge(
                    old_value,
                    new_value,
                )
            else:
                result[key] = new_value

        return result

    def print_summary(
        self,
        totals: dict,
        dry_run: bool,
    ):
        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Résumé de l'import"
            )
        )

        self.stdout.write(
            f"Fichiers traités          : "
            f"{totals['files']}"
        )

        self.stdout.write(
            f"Matières créées           : "
            f"{totals['subjects_created']}"
        )

        self.stdout.write(
            f"Chapitres créés           : "
            f"{totals['chapters_created']}"
        )

        self.stdout.write(
            f"Filières créées           : "
            f"{totals['branches_created']}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Questions créées          : "
                f"{totals['questions_created']}"
            )
        )

        self.stdout.write(
            "Questions mises à jour     : "
            f"{totals['questions_updated']}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Questions avec solution   : "
                f"{totals['questions_with_solution']}"
            )
        )

        self.stdout.write(
            "Questions sans solution    : "
            f"{totals['questions_without_solution']}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Questions avec graphe      : "
                f"{totals['questions_with_graph']}"
            )
        )

        self.stdout.write(
            "Questions sans graphe       : "
            f"{totals['questions_without_graph']}"
        )

        self.stdout.write(
            "Questions désactivées      : "
            f"{totals['questions_deactivated']}"
        )

        if totals["errors"]:
            self.stdout.write(
                self.style.ERROR(
                    f"Erreurs                   : "
                    f"{totals['errors']}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Aucune erreur."
                )
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
                    "Import terminé avec succès."
                )
            )