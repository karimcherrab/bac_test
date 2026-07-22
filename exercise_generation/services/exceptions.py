class ExerciseGenerationError(Exception):
    """خطأ عام أثناء إنشاء التمرين."""


class AxisNotFoundError(ExerciseGenerationError):
    """المحور غير موجود أو غير نشط."""


class EmptyAxisContentError(ExerciseGenerationError):
    """محتوى المحور فارغ أو غير صالح."""


class ExerciseParsingError(ExerciseGenerationError):
    """إجابة النموذج ليست JSON صالحًا."""


class ExerciseValidationError(ExerciseGenerationError):
    """التمرين الناتج لا يحترم البنية المطلوبة."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []
