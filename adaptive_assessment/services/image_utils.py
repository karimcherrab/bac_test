import io
import uuid
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover
    Image = None
    ImageOps = None
    UnidentifiedImageError = Exception


class SolutionImageError(ValueError):
    pass


@dataclass
class PreparedImage:
    content: bytes
    mime_type: str
    width: int
    height: int
    original_name: str


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_DIMENSION = 2000
JPEG_QUALITY = 86
MAX_IMAGES = 5


def prepare_solution_images(uploaded_files):
    files = list(uploaded_files or [])
    if not files:
        raise SolutionImageError("أضف صورة واحدة على الأقل لحلك.")
    if len(files) > MAX_IMAGES:
        raise SolutionImageError(f"يمكن إرسال {MAX_IMAGES} صور كحد أقصى للحل الواحد.")
    if Image is None:
        raise SolutionImageError("مكتبة معالجة الصور غير مثبتة على الخادم. ثبّت Pillow.")

    prepared = []
    for uploaded in files:
        content_type = str(getattr(uploaded, "content_type", "") or "").lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise SolutionImageError("صيغة إحدى الصور غير مدعومة. استخدم JPG أو PNG أو WEBP.")

        size = int(getattr(uploaded, "size", 0) or 0)
        if size <= 0:
            raise SolutionImageError("إحدى الصور فارغة.")
        if size > MAX_UPLOAD_BYTES:
            raise SolutionImageError("حجم إحدى الصور كبير جدًا. التقط صورة أوضح بحجم أصغر.")

        try:
            uploaded.seek(0)
            with Image.open(uploaded) as image:
                image.verify()
            uploaded.seek(0)
            with Image.open(uploaded) as image:
                image = ImageOps.exif_transpose(image)
                if image.mode not in ("RGB", "L"):
                    background = Image.new("RGB", image.size, "white")
                    if "A" in image.getbands():
                        background.paste(image, mask=image.getchannel("A"))
                    else:
                        background.paste(image)
                    image = background
                elif image.mode == "L":
                    image = image.convert("RGB")
                else:
                    image = image.convert("RGB")

                image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
                width, height = image.size
                if width < 350 or height < 350:
                    raise SolutionImageError("دقة إحدى الصور منخفضة جدًا. صوّر الورقة من مسافة أقرب.")

                output = io.BytesIO()
                image.save(
                    output,
                    format="JPEG",
                    quality=JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                content = output.getvalue()
        except SolutionImageError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise SolutionImageError("تعذر قراءة إحدى الملفات كصورة سليمة.") from exc
        finally:
            try:
                uploaded.seek(0)
            except Exception:
                pass

        prepared.append(
            PreparedImage(
                content=content,
                mime_type="image/jpeg",
                width=width,
                height=height,
                original_name=str(getattr(uploaded, "name", "solution.jpg") or "solution.jpg")[:180],
            )
        )

    # Keep the full request comfortably below provider image limits after base64 expansion.
    total = sum(len(item.content) for item in prepared)
    if total > 14 * 1024 * 1024:
        raise SolutionImageError(
            "مجموع صور الحل كبير جدًا. صوّر الصفحات بإضاءة جيدة ومن دون خلفية زائدة."
        )
    return prepared


def persist_solution_images(*, prepared_images, student_id, answer_id):
    saved = []
    for index, item in enumerate(prepared_images, start=1):
        storage_name = (
            f"adaptive_answers/{student_id or 'student'}/{answer_id}/"
            f"page_{index}_{uuid.uuid4().hex[:10]}.jpg"
        )
        stored = default_storage.save(storage_name, ContentFile(item.content))
        saved.append(
            {
                "storage_name": stored,
                "page": index,
                "width": item.width,
                "height": item.height,
            }
        )
    return saved


def delete_persisted_images(image_records):
    for record in image_records or []:
        name = record.get("storage_name") if isinstance(record, dict) else ""
        if name:
            try:
                default_storage.delete(name)
            except Exception:
                pass
