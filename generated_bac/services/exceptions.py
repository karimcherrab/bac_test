class BacGenerationError(Exception):
    """خطأ أثناء إنشاء التمرين أو الحل."""


class NoReferenceExercisesError(BacGenerationError):
    """لا توجد تمارين بكالوريا مطابقة للوحدة والشعبة."""


class AIResponseError(BacGenerationError):
    """استجابة الذكاء الاصطناعي غير صالحة."""
