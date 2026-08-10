import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from course.models import Axis, Branch, Chapter, Question, Subject


class Command(BaseCommand):
    """
    Importe des questions depuis un fichier JSON ou un dossier.

    Règle importante :
    - aucune matière n'est créée ;
    - aucun chapitre n'est créé ;
    - aucun axe n'est créé ;
    - aucune filière n'est créée.

    Si subject_code, chapter_code, tag ou branch_code n'existe pas,
    l'import du fichier échoue et aucune donnée n'est enregistrée.

    Structure minimale :

    {
        "subject_code": "math",
        "chapter_code": "numerical_sequences",
        "tag": "seq_monotonicity",
        "title": "اتجاه تغير المتتالية",
        "questions": [...]
    }
    """

    help = (
        "Importe des questions JSON uniquement vers une matière, "
        "un chapitre, un axe et des filières déjà existants."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            "--file",
            dest="input_path",
            type=str,
            required=True,
            help=(
                "Chemin vers un fichier JSON ou un dossier. "
                "Pour un dossier, les sous-dossiers sont parcourus."
            ),
        )

        parser.add_argument(
            "--branch-code",
            type=str,
            default=None,
            help=(
                "Code d'une filière existante utilisée par défaut "
                "pour les questions qui n'ont pas branch_code."
            ),
        )

        parser.add_argument(
            "--replace",
            action="store_true",
            help=(
                "Supprime les anciennes questions de l'axe avant l'import."
            ),
        )

        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Désactive les questions de l'axe absentes du JSON."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valide l'import sans enregistrer.",
        )

    def handle(self, *args, **options):
        input_path = Path(
            options["input_path"]
        ).expanduser().resolve()

        if not input_path.exists():
            raise CommandError(
                f"Chemin introuvable : {input_path}"
            )

        json_files = self.get_json_files(input_path)

        if not json_files:
            raise CommandError(
                f"Aucun fichier JSON trouvé dans : {input_path}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(json_files)} fichier(s) JSON trouvé(s)."
            )
        )

        totals = {
            "files": 0,
            "questions_created": 0,
            "questions_updated": 0,
            "questions_with_solution": 0,
            "questions_without_solution": 0,
            "questions_with_graph": 0,
            "questions_without_graph": 0,
            "questions_with_documents": 0,
            "questions_without_documents": 0,
            "questions_deactivated": 0,
            "errors": 0,
        }

        try:
            # Toute l'importation est atomique.
            # Une erreur de code/tag annule tout.
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
                    transaction.set_rollback(True)

        except Exception as exc:
            raise CommandError(
                f"Échec de l'import. Aucune donnée enregistrée : {exc}"
            ) from exc

        self.print_summary(
            totals=totals,
            dry_run=options["dry_run"],
        )

    def get_json_files(self, input_path: Path) -> list[Path]:
        if input_path.is_file():
            if input_path.suffix.lower() != ".json":
                raise CommandError(
                    "Le fichier doit avoir l'extension .json."
                )

            return [input_path]

        return sorted(
            path
            for path in input_path.rglob("*.json")
            if path.is_file()
        )

    def load_json(self, json_path: Path) -> dict:
        try:
            with json_path.open(
                mode="r",
                encoding="utf-8-sig",
            ) as file:
                data = json.load(file)

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

        except OSError as exc:
            raise CommandError(
                f"Impossible de lire {json_path.name} : {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise CommandError(
                f"La racine de {json_path.name} doit être un objet JSON."
            )

        return data

    def import_file(
        self,
        json_file: Path,
        options: dict,
    ) -> dict:
        root = self.load_json(json_file)

        self.validate_root(
            root=root,
            json_file=json_file,
        )

        # Vérification stricte avant toute suppression ou création.
        subject = self.get_existing_subject(root)
        chapter = self.get_existing_chapter(
            root=root,
            subject=subject,
        )
        axis = self.get_existing_axis(
            root=root,
            subject=subject,
            chapter=chapter,
        )
        default_branch = self.get_existing_default_branch(
            options.get("branch_code")
        )

        questions = root["questions"]

        file_totals = {
            "questions_created": 0,
            "questions_updated": 0,
            "questions_with_solution": 0,
            "questions_without_solution": 0,
            "questions_with_graph": 0,
            "questions_without_graph": 0,
            "questions_with_documents": 0,
            "questions_without_documents": 0,
            "questions_deactivated": 0,
            "errors": 0,
        }

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

        # Ne supprimer qu'après validation de tous les codes principaux.
        if options["replace"]:
            deleted_count, _ = Question.objects.filter(
                axis=axis,
            ).delete()

            self.stdout.write(
                self.style.WARNING(
                    f"{deleted_count} ancienne(s) entrée(s) supprimée(s)."
                )
            )

        imported_codes: set[str] = set()

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

                question_code = normalized.pop("code")
                imported_codes.add(question_code)

                question, created = Question.objects.update_or_create(
                    axis=axis,
                    code=question_code,
                    defaults=normalized,
                )

                question.full_clean()
                question.save()

                if created:
                    file_totals["questions_created"] += 1
                    status = "créée"
                else:
                    file_totals["questions_updated"] += 1
                    status = "mise à jour"

                if self.has_solution(question.solution):
                    file_totals["questions_with_solution"] += 1
                    solution_status = "avec solution"
                else:
                    file_totals["questions_without_solution"] += 1
                    solution_status = "sans solution"

                if self.has_graph(question.graph_data):
                    file_totals["questions_with_graph"] += 1
                    graph_status = "avec graphe"
                else:
                    file_totals["questions_without_graph"] += 1
                    graph_status = "sans graphe"

                documents = getattr(
                    question,
                    "documents",
                    None,
                )

                if documents is None:
                    question_metadata = (
                        question.metadata
                        if isinstance(question.metadata, dict)
                        else {}
                    )
                    documents = question_metadata.get(
                        "documents",
                        [],
                    )

                if self.has_documents(documents):
                    file_totals["questions_with_documents"] += 1
                    document_status = "avec document(s)"
                else:
                    file_totals["questions_without_documents"] += 1
                    document_status = "sans document"

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {question_code} : {status}, "
                        f"{solution_status}, {graph_status}, "
                        f"{document_status}"
                    )
                )

            except Exception as exc:
                file_totals["errors"] += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"  ✗ Question {position} : {exc}"
                    )
                )

                # Important : aucune importation partielle.
                raise CommandError(
                    f"Erreur dans la question {position} "
                    f"de {json_file.name}."
                ) from exc

        if options["deactivate_missing"]:
            missing_questions = Question.objects.filter(
                axis=axis,
                is_active=True,
            )

            if imported_codes:
                missing_questions = missing_questions.exclude(
                    code__in=imported_codes,
                )

            deactivated_count = missing_questions.update(
                is_active=False,
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
        required_fields = [
            "subject_code",
            "chapter_code",
            "tag",
            "title",
            "questions",
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in root
        ]

        if missing_fields:
            raise CommandError(
                f"{json_file.name} ne contient pas : "
                f"{', '.join(missing_fields)}"
            )

        for field in [
            "subject_code",
            "chapter_code",
            "tag",
            "title",
        ]:
            if not self.clean_string(root.get(field)):
                raise CommandError(
                    f"{json_file.name} : {field} est vide."
                )

        if not isinstance(root["questions"], list):
            raise CommandError(
                f"{json_file.name} : questions doit être une liste."
            )

        if not root["questions"]:
            raise CommandError(
                f"{json_file.name} : questions est vide."
            )

    def get_existing_subject(self, root: dict) -> Subject:
        subject_code = self.clean_string(
            root["subject_code"]
        )

        subject = Subject.objects.filter(
            code=subject_code,
        ).first()

        if subject is None:
            raise CommandError(
                f"La matière avec le code '{subject_code}' "
                "n'existe pas. Aucune donnée ne sera ajoutée."
            )

        return subject

    def get_existing_chapter(
        self,
        root: dict,
        subject: Subject,
    ) -> Chapter:
        chapter_code = self.clean_string(
            root["chapter_code"]
        )

        chapter = Chapter.objects.filter(
            subject=subject,
            code=chapter_code,
        ).first()

        if chapter is None:
            raise CommandError(
                f"Le chapitre '{chapter_code}' n'existe pas "
                f"dans la matière '{subject.code}'. "
                "Aucune donnée ne sera ajoutée."
            )

        if hasattr(chapter, "is_active") and not chapter.is_active:
            raise CommandError(
                f"Le chapitre '{chapter_code}' existe, "
                "mais il est désactivé."
            )

        return chapter

    def get_existing_axis(
        self,
        root: dict,
        subject: Subject,
        chapter: Chapter,
    ) -> Axis:
        axis_tag = self.clean_string(root["tag"])

        axis = (
            Axis.objects
            .select_related(
                "chapter",
                "chapter__subject",
            )
            .filter(
                chapter=chapter,
                chapter__subject=subject,
                tag=axis_tag,
            )
            .first()
        )

        if axis is None:
            raise CommandError(
                f"L'axe avec le tag '{axis_tag}' n'existe pas "
                f"dans le chapitre '{chapter.code}' "
                f"de la matière '{subject.code}'. "
                "Aucune donnée ne sera ajoutée."
            )

        if not axis.is_active:
            raise CommandError(
                f"L'axe '{axis_tag}' existe, "
                "mais il est désactivé."
            )

        root_title = self.clean_string(
            root.get("title")
        )

        # Le titre ne sert pas à trouver l'axe.
        # On avertit seulement s'il est différent.
        if root_title and axis.title != root_title:
            self.stdout.write(
                self.style.WARNING(
                    f"Attention : le titre JSON '{root_title}' "
                    f"est différent du titre DB '{axis.title}'. "
                    "Le titre DB n'est pas modifié."
                )
            )

        return axis

    def get_existing_default_branch(
        self,
        branch_code: str | None,
    ) -> Branch | None:
        if not branch_code:
            return None

        normalized_code = self.clean_string(
            branch_code
        )

        branch = Branch.objects.filter(
            code__iexact=normalized_code,
        ).first()

        if branch is None:
            raise CommandError(
                f"La filière avec le code '{normalized_code}' "
                "n'existe pas. Aucune filière ne sera créée."
            )

        return branch

    def normalize_question(
        self,
        raw_question: Any,
        root: dict,
        json_file: Path,
        position: int,
        default_branch: Branch | None,
    ) -> dict:
        if not isinstance(raw_question, dict):
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
                f"Le texte de la question '{code}' est vide."
            )

        root_tag = self.clean_string(
            root.get("tag")
        )
        question_tag = self.clean_string(
            raw_question.get("tag")
        )

        if question_tag and question_tag != root_tag:
            raise ValueError(
                f"Tag incorrect pour '{code}' : "
                f"{question_tag} != {root_tag}"
            )

        context = self.clean_string(
            raw_question.get("context")
        )

        standalone_text = self.clean_string(
            raw_question.get("standalone_text")
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

        solution = self.normalize_solution_json(
            solution_data=raw_question.get("solution"),
            question_code=code,
        )

        graph_data = self.normalize_graph_json(
            graph_data=raw_question.get("graph_data"),
            question_code=code,
        )

        documents = self.normalize_documents_json(
            documents_data=raw_question.get("documents"),
            question_code=code,
        )

        metadata = raw_question.get(
            "metadata",
            {},
        )

        if not isinstance(metadata, dict):
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
                raw_question.get("source_numbers")
            ),
            "imported_from": json_file.name,
            "json_version": root.get("version", 1),
            "language": root.get("language", "ar"),
            "direction": root.get("direction", "rtl"),
        }

        normalized_question = {
            "code": code,
            "branch": self.resolve_question_branch(
                raw_question=raw_question,
                default_branch=default_branch,
            ),
            "number": self.clean_string(
                raw_question.get("number")
            ),
            "exercise": self.clean_string(
                raw_question.get("exercise")
            ),
            "title": self.clean_string(
                raw_question.get("title")
                or raw_question.get("skill")
            ),
            "text": text,
            "standalone_text": standalone_text,
            "context": context,
            "standalone_support": self.ensure_list(
                raw_question.get("standalone_support")
            ),
            "original_text": original_text,
            "question_type": self.normalize_question_type(
                raw_question.get("question_type")
                or raw_question.get("type")
                or "bac"
            ),
            "difficulty": self.normalize_difficulty(
                raw_question.get("difficulty")
            ),
            "skill": self.clean_string(
                raw_question.get("skill")
            ),
            "year": self.optional_positive_integer(
                raw_question.get("year"),
                field_name="year",
            ),
            "source_file": self.clean_string(
                raw_question.get("source_file")
                or root.get("source_file")
                or json_file.name
            ),
            "source_page": self.optional_positive_integer(
                raw_question.get("source_page"),
                field_name="source_page",
            ),
            "secondary_tags": self.ensure_list(
                raw_question.get("secondary_tags")
            ),
            "depends_on": self.ensure_list(
                raw_question.get("depends_on")
            ),
            "images": self.ensure_list(
                raw_question.get("images")
            ),
            "solution": solution,
            "graph_data": graph_data,
            "metadata": metadata,
            "is_standalone": self.normalize_boolean(
                raw_question.get("is_standalone"),
                default=True,
            ),
            "is_active": self.normalize_boolean(
                raw_question.get("is_active"),
                default=True,
            ),
            "order": (
                self.optional_positive_integer(
                    raw_question.get("order"),
                    field_name="order",
                )
                or position
            ),
        }

        model_field_names = {
            field.name
            for field in Question._meta.get_fields()
        }

        if "documents" in model_field_names:
            normalized_question["documents"] = documents
        else:
            normalized_question["metadata"]["documents"] = documents

        if "has_documents" in model_field_names:
            normalized_question["has_documents"] = bool(documents)
        else:
            normalized_question["metadata"]["has_documents"] = bool(documents)

        if "document_count" in model_field_names:
            normalized_question["document_count"] = len(documents)
        else:
            normalized_question["metadata"]["document_count"] = len(documents)

        return normalized_question

    def resolve_question_branch(
        self,
        raw_question: dict,
        default_branch: Branch | None,
    ) -> Branch | None:
        branch_value = (
            raw_question.get("branch_code")
            or raw_question.get("branch")
        )

        if not branch_value:
            return default_branch

        if isinstance(branch_value, dict):
            branch_code = self.clean_string(
                branch_value.get("code")
            )
        else:
            branch_code = self.clean_string(
                branch_value
            )

        if not branch_code:
            return default_branch

        branch = Branch.objects.filter(
            code__iexact=branch_code,
        ).first()

        if branch is None:
            raise ValueError(
                f"La filière '{branch_code}' n'existe pas. "
                "Aucune filière ne sera créée."
            )

        return branch

    def normalize_solution_json(
        self,
        solution_data: Any,
        question_code: str,
    ) -> dict:
        if solution_data in (None, ""):
            return {}

        if isinstance(solution_data, str):
            cleaned = solution_data.strip()

            return {
                "simple_solution": {
                    "explanation": cleaned,
                    "final_answer": cleaned,
                },
                "detailed_explanation": cleaned,
                "final_answer": cleaned,
                "is_complete": True,
            }

        if not isinstance(solution_data, dict):
            raise ValueError(
                f"La solution de '{question_code}' "
                "doit être un objet JSON."
            )

        normalized = self.deep_copy_json_value(
            solution_data
        )

        if "steps" in normalized:
            if normalized["steps"] is None:
                normalized["steps"] = []
            elif not isinstance(
                normalized["steps"],
                list,
            ):
                normalized["steps"] = [
                    normalized["steps"]
                ]

        for list_field in [
            "hints",
            "common_mistakes",
            "bac_writing",
            "understanding_check",
        ]:
            if list_field in normalized:
                normalized[list_field] = self.ensure_list(
                    normalized.get(list_field)
                )

        normalized.setdefault(
            "is_complete",
            True,
        )

        return normalized

    def normalize_documents_json(
        self,
        documents_data: Any,
        question_code: str,
    ) -> list:
        if documents_data in (None, ""):
            return []

        if not isinstance(documents_data, list):
            raise ValueError(
                f"Le champ documents de '{question_code}' "
                "doit être une liste JSON."
            )

        normalized_documents = self.deep_copy_json_value(
            documents_data
        )

        for index, document in enumerate(
            normalized_documents,
            start=1,
        ):
            if not isinstance(document, dict):
                raise ValueError(
                    f"Le document {index} de '{question_code}' "
                    "doit être un objet JSON."
                )

            document.setdefault(
                "id",
                f"{question_code}_document_{index}",
            )
            document.setdefault(
                "type",
                "document",
            )

        return normalized_documents

    def normalize_graph_json(
        self,
        graph_data: Any,
        question_code: str,
    ) -> dict:
        if graph_data in (None, ""):
            return {}

        if not isinstance(graph_data, dict):
            raise ValueError(
                f"Le graphe de '{question_code}' "
                "doit être un objet JSON."
            )

        return self.deep_copy_json_value(
            graph_data
        )

    def update_axis_content(
        self,
        axis: Axis,
        root: dict,
    ):
        current_content = (
            axis.content
            if isinstance(axis.content, dict)
            else {}
        )

        axis.content = self.deep_merge(
            current_content,
            self.build_axis_content(root),
        )

        axis.save(
            update_fields=["content"]
        )

    def build_axis_content(self, root: dict) -> dict:
        return {
            "version": root.get("version", 1),
            "language": root.get("language", "ar"),
            "direction": root.get("direction", "rtl"),
            "subject_code": root.get(
                "subject_code",
                "",
            ),
            "chapter_code": root.get(
                "chapter_code",
                "",
            ),
            "axis_tag": root.get("tag", ""),
            "axis_title": root.get("title", ""),
            "source_file": root.get(
                "source_file",
                "",
            ),
            "question_count": len(
                root.get("questions", [])
            ),
            "years": self.ensure_list(
                root.get("years")
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
        return "\n\n".join(
            part.strip()
            for part in [context, text]
            if part and part.strip()
        )

    def has_solution(self, solution: Any) -> bool:
        return bool(
            isinstance(solution, dict)
            and solution
        )

    def has_graph(self, graph_data: Any) -> bool:
        return bool(
            isinstance(graph_data, dict)
            and graph_data
        )

    def has_documents(self, documents: Any) -> bool:
        return bool(
            isinstance(documents, list)
            and documents
        )

    def normalize_question_type(
        self,
        value: Any,
    ) -> str:
        normalized = self.clean_string(value).lower()

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

        if normalized not in {
            "bac",
            "guided",
            "practice",
            "quiz",
        }:
            return "bac"

        return normalized

    def normalize_difficulty(
        self,
        value: Any,
    ) -> str:
        normalized = self.clean_string(
            value or "medium"
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

        if isinstance(value, bool):
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
        if value in (None, ""):
            return None

        if isinstance(value, bool):
            raise ValueError(
                f"{field_name} doit être un entier."
            )

        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} doit être un entier."
            ) from exc

        if result < 0:
            raise ValueError(
                f"{field_name} ne peut pas être négatif."
            )

        return result

    def ensure_list(self, value: Any) -> list:
        if value in (None, ""):
            return []

        if isinstance(value, list):
            return value

        return [value]

    def clean_string(self, value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def deep_copy_json_value(
        self,
        value: Any,
    ) -> Any:
        try:
            return json.loads(
                json.dumps(
                    value,
                    ensure_ascii=False,
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "La donnée contient une valeur "
                "incompatible avec JSON."
            ) from exc

    def deep_merge(
        self,
        old_data: dict,
        new_data: dict,
    ) -> dict:
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
            f"Fichiers traités          : {totals['files']}"
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
            self.style.SUCCESS(
                "Questions avec document(s): "
                f"{totals['questions_with_documents']}"
            )
        )
        self.stdout.write(
            "Questions sans document     : "
            f"{totals['questions_without_documents']}"
        )
        self.stdout.write(
            "Questions désactivées       : "
            f"{totals['questions_deactivated']}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Mode dry-run : aucune donnée enregistrée."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Import terminé avec succès."
                )
            )