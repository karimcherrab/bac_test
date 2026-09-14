import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from adaptive_assessment.models import (
    BacIdea,
    BacIdeaVariant,
    Misconception,
    Skill,
)


SUPPORTED_SCHEMA_VERSIONS = {"2.0"}


class BaseBlueprintValidator:
    """
    Lightweight schema validator for Assessment Blueprint JSON v2.

    This validator checks the structure required by the importer.
    It does not depend on a specific axis, branch, chapter, or filename.
    """

    def __init__(self, data):
        self.data = data
        self.errors = []

    def validate(self):
        if not isinstance(self.data, dict):
            self.errors.append("JSON root must be an object.")
            return self.errors

        self._validate_schema_version()
        self._validate_identity()
        self._validate_skills()
        self._validate_bac_ideas()

        return self.errors

    def _validate_schema_version(self):
        version = str(self.data.get("schema_version") or "").strip()

        if not version:
            self.errors.append("schema_version is required.")
            return

        if version not in SUPPORTED_SCHEMA_VERSIONS:
            self.errors.append(
                f"Unsupported schema_version '{version}'. "
                f"Supported versions: {', '.join(sorted(SUPPORTED_SCHEMA_VERSIONS))}."
            )

    def _validate_identity(self):
        branch = self.data.get("branch")
        axis = self.data.get("axis")

        if not isinstance(branch, dict):
            self.errors.append("branch must be an object.")
        elif not str(branch.get("code") or "").strip():
            self.errors.append("branch.code is required.")

        if not isinstance(axis, dict):
            self.errors.append("axis must be an object.")
        elif not (
            str(axis.get("tag") or "").strip()
            or str(axis.get("code") or "").strip()
        ):
            self.errors.append("axis.tag or axis.code is required.")

    def _validate_skills(self):
        skills = self.data.get("skills")

        if skills is None:
            self.errors.append("skills is required.")
            return

        if not isinstance(skills, list):
            self.errors.append("skills must be an array.")
            return

        skill_codes = set()
        idea_codes_global = set()

        for i, skill in enumerate(skills):
            path = f"skills[{i}]"

            if not isinstance(skill, dict):
                self.errors.append(f"{path} must be an object.")
                continue

            skill_code = (
                skill.get("skill_code")
                or skill.get("code")
                or ""
            ).strip()

            if not skill_code:
                self.errors.append(
                    f"{path}.skill_code is required."
                )
            elif skill_code in skill_codes:
                self.errors.append(
                    f"{path}.skill_code duplicates '{skill_code}'."
                )
            else:
                skill_codes.add(skill_code)

            ideas = skill.get("ideas", [])

            if not isinstance(ideas, list):
                self.errors.append(f"{path}.ideas must be an array.")
                continue

            local_idea_codes = set()

            for j, idea in enumerate(ideas):
                idea_path = f"{path}.ideas[{j}]"

                if not isinstance(idea, dict):
                    self.errors.append(
                        f"{idea_path} must be an object."
                    )
                    continue

                idea_code = (
                    idea.get("idea_code")
                    or idea.get("code")
                    or ""
                ).strip()

                if not idea_code:
                    self.errors.append(
                        f"{idea_path}.idea_code is required."
                    )
                    continue

                if idea_code in local_idea_codes:
                    self.errors.append(
                        f"{idea_path}.idea_code duplicates "
                        f"'{idea_code}' inside skill '{skill_code}'."
                    )
                else:
                    local_idea_codes.add(idea_code)

                if idea_code in idea_codes_global:
                    self.errors.append(
                        f"{idea_path}.idea_code '{idea_code}' "
                        "must be globally unique across skills."
                    )
                else:
                    idea_codes_global.add(idea_code)

            self._validate_common_errors(
                skill.get("common_errors", []),
                f"{path}.common_errors",
            )

    def _validate_bac_ideas(self):
        bac_ideas = self.data.get("bac_ideas")

        if bac_ideas is None:
            self.errors.append("bac_ideas is required.")
            return

        if not isinstance(bac_ideas, list):
            self.errors.append("bac_ideas must be an array.")
            return

        idea_codes = set()
        variant_codes_global = set()

        for i, idea in enumerate(bac_ideas):
            path = f"bac_ideas[{i}]"

            if not isinstance(idea, dict):
                self.errors.append(f"{path} must be an object.")
                continue

            idea_code = (
                idea.get("idea_code")
                or idea.get("code")
                or ""
            ).strip()

            if not idea_code:
                self.errors.append(
                    f"{path}.idea_code is required."
                )
            elif idea_code in idea_codes:
                self.errors.append(
                    f"{path}.idea_code duplicates '{idea_code}'."
                )
            else:
                idea_codes.add(idea_code)

            variants = idea.get("variants", [])

            if not isinstance(variants, list):
                self.errors.append(
                    f"{path}.variants must be an array."
                )
                continue

            local_variant_codes = set()

            for j, variant in enumerate(variants):
                variant_path = f"{path}.variants[{j}]"

                if not isinstance(variant, dict):
                    self.errors.append(
                        f"{variant_path} must be an object."
                    )
                    continue

                variant_code = (
                    variant.get("variant_code")
                    or variant.get("code")
                    or ""
                ).strip()

                if not variant_code:
                    self.errors.append(
                        f"{variant_path}.variant_code is required."
                    )
                    continue

                if variant_code in local_variant_codes:
                    self.errors.append(
                        f"{variant_path}.variant_code duplicates "
                        f"'{variant_code}' in BAC idea '{idea_code}'."
                    )
                else:
                    local_variant_codes.add(variant_code)

                if variant_code in variant_codes_global:
                    self.errors.append(
                        f"{variant_path}.variant_code "
                        f"'{variant_code}' must be globally unique."
                    )
                else:
                    variant_codes_global.add(variant_code)

            self._validate_common_errors(
                idea.get("common_errors", []),
                f"{path}.common_errors",
            )

    def _validate_common_errors(self, errors, path):
        if not isinstance(errors, list):
            self.errors.append(f"{path} must be an array.")
            return

        seen = set()

        for i, error in enumerate(errors):
            error_path = f"{path}[{i}]"

            if not isinstance(error, dict):
                self.errors.append(
                    f"{error_path} must be an object."
                )
                continue

            code = str(error.get("code") or "").strip()

            if not code:
                self.errors.append(
                    f"{error_path}.code is required."
                )
                continue

            if code in seen:
                self.errors.append(
                    f"{error_path}.code duplicates '{code}'."
                )
            else:
                seen.add(code)


class Command(BaseCommand):
    help = (
        "Import an Assessment Blueprint JSON v2 into "
        "adaptive_assessment tables."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Path to the complete assessment blueprint JSON file.",
        )

        parser.add_argument(
            "--axis-id",
            type=int,
            default=None,
            help="Optional Axis primary key override.",
        )

        parser.add_argument(
            "--axis-tag",
            type=str,
            default="",
            help="Optional Axis tag/code override.",
        )

        parser.add_argument(
            "--branch-code",
            type=str,
            default="",
            help="Optional Branch code override.",
        )

        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Skip blueprint structure validation.",
        )

        parser.add_argument(
            "--no-disable-missing",
            action="store_true",
            help=(
                "Do not deactivate existing variants/misconceptions "
                "that are absent from the imported JSON."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        data = self._load_json(options["json_path"])

        if not options["skip_validation"]:
            self._validate_blueprint(data)

        AxisModel = Skill._meta.get_field(
            "axis"
        ).remote_field.model

        BranchModel = BacIdea._meta.get_field(
            "branch"
        ).remote_field.model

        axis = self._resolve_axis(
            AxisModel=AxisModel,
            data=data,
            axis_id=options.get("axis_id"),
            axis_tag=options.get("axis_tag"),
        )

        branch = self._resolve_branch(
            BranchModel=BranchModel,
            data=data,
            branch_code=options.get("branch_code"),
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Axis: {axis} | Branch: {branch}"
            )
        )

        skill_stats = self._import_skills(
            axis=axis,
            data=data,
            disable_missing=not options["no_disable_missing"],
        )

        bac_stats = self._import_bac_ideas(
            axis=axis,
            branch=branch,
            data=data,
            disable_missing=not options["no_disable_missing"],
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Import completed successfully."))
        self.stdout.write(
            f"Skills: {skill_stats['created']} created, "
            f"{skill_stats['updated']} updated"
        )
        self.stdout.write(
            f"Skill misconceptions: "
            f"{skill_stats['misconceptions']} imported/updated"
        )
        self.stdout.write(
            f"BAC ideas: {bac_stats['created']} created, "
            f"{bac_stats['updated']} updated"
        )
        self.stdout.write(
            f"Variants: {bac_stats['variants']} imported/updated"
        )
        self.stdout.write(
            f"BAC misconceptions: "
            f"{bac_stats['misconceptions']} imported/updated"
        )

    def _load_json(self, path):
        file_path = Path(path)

        if not file_path.exists():
            raise CommandError(
                f"File not found: {file_path}"
            )

        if not file_path.is_file():
            raise CommandError(
                f"Path is not a file: {file_path}"
            )

        try:
            with file_path.open(
                "r",
                encoding="utf-8-sig",
            ) as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise CommandError(
                f"Invalid JSON in {file_path}: "
                f"line {exc.lineno}, column {exc.colno}: "
                f"{exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise CommandError(
                "JSON root must be an object."
            )

        return data

    def _validate_blueprint(self, data):
        validator = BaseBlueprintValidator(data)
        errors = validator.validate()

        if not errors:
            self.stdout.write(
                self.style.SUCCESS(
                    "Blueprint structure validation passed."
                )
            )
            return

        message = [
            "Assessment Blueprint validation failed:",
            "",
        ]

        for error in errors:
            message.append(f"- {error}")

        raise CommandError("\n".join(message))

    def _resolve_axis(
        self,
        AxisModel,
        data,
        axis_id=None,
        axis_tag="",
    ):
        if axis_id is not None:
            try:
                return AxisModel.objects.get(pk=axis_id)
            except AxisModel.DoesNotExist as exc:
                raise CommandError(
                    f"Axis with id={axis_id} does not exist."
                ) from exc

        axis_data = data.get("axis") or {}

        identifier = (
            str(axis_tag or "").strip()
            or str(axis_data.get("tag") or "").strip()
            or str(axis_data.get("code") or "").strip()
        )

        if not identifier:
            raise CommandError(
                "Cannot resolve Axis. "
                "Use axis.tag/axis.code in JSON or pass --axis-id."
            )

        field_names = {
            field.name
            for field in AxisModel._meta.get_fields()
            if getattr(field, "concrete", False)
        }

        lookup_fields = []

        for field_name in (
            "tag",
            "code",
            "slug",
            "key",
        ):
            if field_name in field_names:
                lookup_fields.append(field_name)

        for field_name in lookup_fields:
            obj = AxisModel.objects.filter(
                **{field_name: identifier}
            ).first()

            if obj:
                return obj

        available = ", ".join(lookup_fields) or "none"

        raise CommandError(
            f"Axis '{identifier}' was not found in "
            f"{AxisModel._meta.label}. "
            f"Detected identifier fields: {available}. "
            "Create the Axis first or pass --axis-id."
        )

    def _resolve_branch(
        self,
        BranchModel,
        data,
        branch_code="",
    ):
        branch_data = data.get("branch") or {}

        code = (
            str(branch_code or "").strip()
            or str(branch_data.get("code") or "").strip()
        )

        if not code:
            raise CommandError(
                "Cannot resolve Branch. "
                "Use branch.code in JSON or pass --branch-code."
            )

        try:
            return BranchModel.objects.get(code=code)
        except BranchModel.DoesNotExist as exc:
            raise CommandError(
                f"Branch code '{code}' does not exist in "
                f"{BranchModel._meta.label}."
            ) from exc

    def _import_skills(
        self,
        axis,
        data,
        disable_missing=True,
    ):
        skills = data.get("skills", [])

        stats = {
            "created": 0,
            "updated": 0,
            "misconceptions": 0,
        }

        imported_skill_codes = set()

        for skill_data in skills:
            skill_code = (
                skill_data.get("skill_code")
                or skill_data.get("code")
                or ""
            ).strip()

            imported_skill_codes.add(skill_code)

            ideas_payload = self._build_skill_ideas_payload(
                skill_data
            )

            defaults = {
                "name": (
                    skill_data.get("title")
                    or skill_data.get("name")
                    or skill_code
                ),
                "description": skill_data.get(
                    "description",
                    "",
                ),
                "order": self._safe_int(
                    skill_data.get("order"),
                    default=0,
                ),
                "ideas": ideas_payload,
                "is_active": True,
            }

            skill, created = Skill.objects.update_or_create(
                axis=axis,
                code=skill_code,
                defaults=defaults,
            )

            if created:
                stats["created"] += 1
            else:
                stats["updated"] += 1

            misconception_count = (
                self._import_skill_misconceptions(
                    axis=axis,
                    skill=skill,
                    errors=skill_data.get(
                        "common_errors",
                        [],
                    ),
                    disable_missing=disable_missing,
                )
            )

            stats["misconceptions"] += misconception_count

        if disable_missing:
            Skill.objects.filter(
                axis=axis
            ).exclude(
                code__in=imported_skill_codes
            ).update(
                is_active=False
            )

        return stats

    def _build_skill_ideas_payload(
        self,
        skill_data,
    ):
        payload = []

        for idea in skill_data.get("ideas", []) or []:
            idea_code = (
                idea.get("idea_code")
                or idea.get("code")
                or ""
            ).strip()

            payload.append(
                {
                    "code": idea_code,
                    "name": (
                        idea.get("title")
                        or idea.get("name")
                        or idea_code
                    ),
                    "description": idea.get(
                        "description",
                        "",
                    ),
                    "difficulty": idea.get(
                        "difficulty",
                        "easy",
                    ),
                    "source": idea.get(
                        "source",
                        "axis_lesson",
                    ),
                    "generation_guidance": (
                        idea.get(
                            "generation_guidance",
                            {},
                        )
                        or {}
                    ),
                }
            )

        return payload

    def _import_skill_misconceptions(
        self,
        axis,
        skill,
        errors,
        disable_missing=True,
    ):
        imported_codes = set()
        count = 0

        for error in errors or []:
            code = str(
                error.get("code") or ""
            ).strip()

            if not code:
                continue

            imported_codes.add(code)

            Misconception.objects.update_or_create(
                axis=axis,
                code=code,
                defaults={
                    "description": error.get(
                        "description",
                        "",
                    ),
                    "severity": error.get(
                        "severity",
                        "medium",
                    ),
                    "skill": skill,
                    "bac_idea": None,
                    "related_skill_idea_codes": (
                        error.get(
                            "related_skill_idea_codes",
                            [],
                        )
                        or []
                    ),
                    "is_active": True,
                },
            )

            count += 1

        if disable_missing:
            Misconception.objects.filter(
                axis=axis,
                skill=skill,
                bac_idea__isnull=True,
            ).exclude(
                code__in=imported_codes
            ).update(
                is_active=False
            )

        return count

    def _import_bac_ideas(
        self,
        axis,
        branch,
        data,
        disable_missing=True,
    ):
        items = data.get("bac_ideas", [])

        stats = {
            "created": 0,
            "updated": 0,
            "variants": 0,
            "misconceptions": 0,
        }

        imported_bac_codes = set()

        for item in items:
            code = (
                item.get("idea_code")
                or item.get("code")
                or ""
            ).strip()

            imported_bac_codes.add(code)

            difficulty = (
                item.get("difficulty_range")
                or {}
            )

            defaults = {
                "title": (
                    item.get("title")
                    or code
                ),
                "description": item.get(
                    "description",
                    "",
                ),
                "priority": item.get(
                    "bac_priority",
                    "medium",
                ),
                "frequency_level": item.get(
                    "frequency_level",
                    "medium",
                ),
                "occurrence_count": self._safe_int(
                    item.get("occurrence_count"),
                    default=0,
                ),
                "years": item.get(
                    "years",
                    [],
                ) or [],
                "required_skills": (
                    item.get("required_skills")
                    or self._flatten_skill_refs(
                        item.get("skill_refs")
                    )
                ),
                "prerequisites": item.get(
                    "prerequisites",
                    [],
                ) or [],
                "external_prerequisites": item.get(
                    "external_prerequisites",
                    [],
                ) or [],
                "difficulty_min": self._safe_int(
                    difficulty.get("min"),
                    default=1,
                ),
                "difficulty_max": self._safe_int(
                    difficulty.get("max"),
                    default=3,
                ),
                "bac_occurrences": item.get(
                    "bac_occurrences",
                    [],
                ) or [],
                "mastery_requirements": item.get(
                    "mastery_requirements",
                    {},
                ) or {},
                "generation_guidance": item.get(
                    "generation_guidance",
                    {},
                ) or {},
                "is_active": True,
            }

            idea, created = BacIdea.objects.update_or_create(
                axis=axis,
                branch=branch,
                code=code,
                defaults=defaults,
            )

            if created:
                stats["created"] += 1
            else:
                stats["updated"] += 1

            stats["variants"] += self._import_variants(
                idea=idea,
                variants=item.get(
                    "variants",
                    [],
                ),
                disable_missing=disable_missing,
            )

            stats["misconceptions"] += (
                self._import_bac_misconceptions(
                    axis=axis,
                    bac_idea=idea,
                    errors=item.get(
                        "common_errors",
                        [],
                    ),
                    disable_missing=disable_missing,
                )
            )

        if disable_missing:
            BacIdea.objects.filter(
                axis=axis,
                branch=branch,
            ).exclude(
                code__in=imported_bac_codes
            ).update(
                is_active=False
            )

        return stats

    def _import_variants(
        self,
        idea,
        variants,
        disable_missing=True,
    ):
        imported_codes = set()
        count = 0

        for variant_data in variants or []:
            code = (
                variant_data.get("variant_code")
                or variant_data.get("code")
                or ""
            ).strip()

            imported_codes.add(code)

            BacIdeaVariant.objects.update_or_create(
                bac_idea=idea,
                code=code,
                defaults={
                    "title": (
                        variant_data.get("title")
                        or code
                    ),
                    "description": variant_data.get(
                        "description",
                        "",
                    ),
                    "years": variant_data.get(
                        "years",
                        [],
                    ) or [],
                    "occurrence_count": self._safe_int(
                        variant_data.get(
                            "occurrence_count"
                        ),
                        default=0,
                    ),
                    "difficulty": self._safe_int(
                        variant_data.get(
                            "difficulty"
                        ),
                        default=1,
                    ),
                    "required_skills": (
                        variant_data.get(
                            "required_skills"
                        )
                        or variant_data.get(
                            "skill_idea_codes",
                            [],
                        )
                        or []
                    ),
                    "distinguishing_feature": (
                        variant_data.get(
                            "distinguishing_feature",
                            "",
                        )
                    ),
                    "is_active": True,
                },
            )

            count += 1

        if disable_missing:
            idea.variants.exclude(
                code__in=imported_codes
            ).update(
                is_active=False
            )

        return count

    def _import_bac_misconceptions(
        self,
        axis,
        bac_idea,
        errors,
        disable_missing=True,
    ):
        imported_codes = set()
        count = 0

        for error in errors or []:
            code = str(
                error.get("code") or ""
            ).strip()

            if not code:
                continue

            imported_codes.add(code)

            Misconception.objects.update_or_create(
                axis=axis,
                code=code,
                defaults={
                    "description": error.get(
                        "description",
                        "",
                    ),
                    "severity": error.get(
                        "severity",
                        "medium",
                    ),
                    "skill": None,
                    "bac_idea": bac_idea,
                    "related_skill_idea_codes": (
                        error.get(
                            "related_skill_idea_codes",
                            [],
                        )
                        or []
                    ),
                    "is_active": True,
                },
            )

            count += 1

        if disable_missing:
            Misconception.objects.filter(
                axis=axis,
                bac_idea=bac_idea,
                skill__isnull=True,
            ).exclude(
                code__in=imported_codes
            ).update(
                is_active=False
            )

        return count

    def _flatten_skill_refs(
        self,
        refs,
    ):
        """
        Convert:

        [
            {
                "skill_code": "SEQ_RECURSIVE_CALC",
                "skill_idea_codes": [
                    "SEQ_REC_INITIAL_TERMS",
                    "SEQ_REC_SUCCESSIVE"
                ]
            }
        ]

        into:

        [
            "SEQ_RECURSIVE_CALC",
            "SEQ_REC_INITIAL_TERMS",
            "SEQ_REC_SUCCESSIVE"
        ]
        """
        if not refs:
            return []

        result = []

        for ref in refs:
            if isinstance(ref, str):
                value = ref.strip()

                if value:
                    result.append(value)

                continue

            if not isinstance(ref, dict):
                continue

            skill_code = str(
                ref.get("skill_code") or ""
            ).strip()

            if skill_code:
                result.append(skill_code)

            for idea_code in (
                ref.get(
                    "skill_idea_codes",
                    [],
                )
                or []
            ):
                idea_code = str(
                    idea_code or ""
                ).strip()

                if idea_code:
                    result.append(idea_code)

        return list(
            dict.fromkeys(result)
        )

    def _safe_int(
        self,
        value,
        default=0,
    ):
        if value is None or value == "":
            return default

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise CommandError(
                f"Expected integer value, got {value!r}."
            ) from exc