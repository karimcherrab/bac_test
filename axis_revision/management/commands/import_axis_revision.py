import json
from pathlib import Path
from typing import Any

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from axis_revision.models import AxisRevision
from course.models import Axis


class Command(BaseCommand):
    help = (
        "استيراد ملف JSON خاص بملخص محور "
        "وإنشائه أو تحديثه في قاعدة البيانات."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="مسار ملف JSON.",
        )

        parser.add_argument(
            "--axis-id",
            type=int,
            default=None,
            help=(
                "معرف المحور. يستعمل إذا لم يكن "
                "axis_tag موجودًا داخل JSON."
            ),
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="تحديث السجل إذا كان موجودًا.",
        )

    def handle(self, *args, **options):
        json_path = Path(
            options["json_path"]
        ).resolve()

        axis_id = options.get("axis_id")
        force = options.get("force", False)

        if not json_path.exists():
            raise CommandError(
                f"الملف غير موجود: {json_path}"
            )

        if not json_path.is_file():
            raise CommandError(
                f"المسار ليس ملفًا: {json_path}"
            )

        if json_path.suffix.lower() != ".json":
            raise CommandError(
                "يجب أن يكون الملف بصيغة JSON."
            )

        data = self.read_json(json_path)

        self.validate_root(data)

        axis = self.get_axis(
            data=data,
            axis_id=axis_id,
        )

        revision = self.save_revision(
            axis=axis,
            data=data,
            file_name=json_path.name,
            force=force,
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "تم استيراد الملخص بنجاح\n"
                    f"Revision ID: {revision.id}\n"
                    f"Axis: {revision.axis.title}\n"
                    f"Tag: {revision.tag}\n"
                    f"Status: {revision.status}"
                )
            )
        )

    @staticmethod
    def read_json(
        json_path: Path,
    ) -> dict[str, Any]:
        try:
            with json_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except UnicodeDecodeError as exc:
            raise CommandError(
                "يجب حفظ الملف بترميز UTF-8."
            ) from exc

        except json.JSONDecodeError as exc:
            raise CommandError(
                (
                    "ملف JSON غير صالح: "
                    f"السطر {exc.lineno}، "
                    f"العمود {exc.colno}: "
                    f"{exc.msg}"
                )
            ) from exc

        if not isinstance(data, dict):
            raise CommandError(
                "الجذر داخل JSON يجب أن يكون object."
            )

        return data

    @staticmethod
    def validate_root(
        data: dict[str, Any],
    ) -> None:
        required_fields = [
            "axis_tag",
            "title",
            "schema_version",
        ]

        missing = [
            field
            for field in required_fields
            if not data.get(field)
        ]

        if missing:
            raise CommandError(
                (
                    "حقول إجبارية ناقصة: "
                    + ", ".join(missing)
                )
            )

        if not isinstance(
            data.get("axis_summary", {}),
            dict,
        ):
            raise CommandError(
                "axis_summary يجب أن يكون object."
            )

        bac_analysis = data.get(
            "bac_analysis",
            {},
        )

        if bac_analysis and not isinstance(
            bac_analysis,
            dict,
        ):
            raise CommandError(
                "bac_analysis يجب أن يكون object."
            )

        decision_tree = data.get(
            "decision_tree",
            {},
        )

        if decision_tree and not isinstance(
            decision_tree,
            dict,
        ):
            raise CommandError(
                "decision_tree يجب أن يكون object."
            )

    @staticmethod
    def get_axis(
        data: dict[str, Any],
        axis_id: int | None,
    ) -> Axis:
        if axis_id is not None:
            try:
                return Axis.objects.get(
                    id=axis_id,
                )
            except Axis.DoesNotExist as exc:
                raise CommandError(
                    (
                        "لا يوجد محور بالمعرف: "
                        f"{axis_id}"
                    )
                ) from exc

        axis_tag = str(
            data.get("axis_tag", "")
        ).strip()

        if not axis_tag:
            raise CommandError(
                (
                    "axis_tag غير موجود داخل JSON. "
                    "استعمل --axis-id."
                )
            )

        try:
            return Axis.objects.get(
                tag=axis_tag,
            )

        except Axis.DoesNotExist as exc:
            raise CommandError(
                (
                    "لم يتم العثور على محور بالـ tag: "
                    f"{axis_tag}"
                )
            ) from exc

        except Axis.MultipleObjectsReturned as exc:
            raise CommandError(
                (
                    "يوجد أكثر من محور بنفس الـ tag: "
                    f"{axis_tag}"
                )
            ) from exc

    @staticmethod
    @transaction.atomic
    def save_revision(
        axis: Axis,
        data: dict[str, Any],
        file_name: str,
        force: bool,
    ) -> AxisRevision:
        revision_tag = str(
            data.get("tag")
            or f"{axis.tag}_revision"
        ).strip()

        existing = AxisRevision.objects.filter(
            axis=axis,
        ).first()

        if existing and not force:
            raise CommandError(
                (
                    "يوجد ملخص لهذا المحور بالفعل. "
                    "استعمل --force لتحديثه."
                )
            )

        defaults = {
            "tag": revision_tag,
            "title": str(
                data.get("title", axis.title)
            ).strip(),
            "subtitle": str(
                data.get("subtitle", "")
            ).strip(),
            "schema_version": str(
                data.get(
                    "schema_version",
                    "1.0",
                )
            ).strip(),
            "language": str(
                data.get("language", "ar")
            ).strip(),
            "direction": str(
                data.get("direction", "rtl")
            ).strip(),
            "math_format": str(
                data.get(
                    "math_format",
                    "LaTeX",
                )
            ).strip(),
            "status": str(
                data.get(
                    "status",
                    "draft",
                )
            ).strip(),
            "order": int(
                data.get(
                    "order",
                    axis.order,
                )
            ),
            "is_active": bool(
                data.get(
                    "is_active",
                    True,
                )
            ),
            "content": data,
            "imported_file_name": file_name,
        }

        revision, _ = (
            AxisRevision.objects.update_or_create(
                axis=axis,
                defaults=defaults,
            )
        )

        return revision