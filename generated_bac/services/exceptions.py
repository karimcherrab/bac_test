class BacGenerationError(Exception):
    """خطأ أثناء إنشاء التمرين أو الحل."""


class NoReferenceExercisesError(BacGenerationError):
    """لا توجد تمارين بكالوريا مطابقة للوحدة والشعبة."""


class AIResponseError(BacGenerationError):
    """استجابة الذكاء الاصطناعي غير صالحة."""


class AIRateLimitError(AIResponseError):
    status_code = 429
    def __init__(self, message, retry_after=30):
        super().__init__(message)
        self.retry_after = retry_after
