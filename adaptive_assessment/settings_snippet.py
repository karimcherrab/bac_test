# settings.py
import os

INSTALLED_APPS += [
    "rest_framework",
    "adaptive_assessment",
]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# You can keep 120b. The application now throttles/retries 429 safely.
GROQ_ASSESSMENT_MODEL = os.getenv(
    "GROQ_ASSESSMENT_MODEL",
    "openai/gpt-oss-120b",
)
GROQ_GRADING_MODEL = os.getenv(
    "GROQ_GRADING_MODEL",
    GROQ_ASSESSMENT_MODEL,
)

# Vision model: reads photographed handwritten solutions.
GROQ_VISION_GRADING_MODEL = os.getenv(
    "GROQ_VISION_GRADING_MODEL",
    "qwen/qwen3.6-27b",
)

# Question visuals need a little more room; retry/backoff still protects low-TPM plans.
GROQ_QUESTION_MAX_COMPLETION_TOKENS = int(
    os.getenv("GROQ_QUESTION_MAX_COMPLETION_TOKENS", "2200")
)
GROQ_GRADING_MAX_COMPLETION_TOKENS = int(
    os.getenv("GROQ_GRADING_MAX_COMPLETION_TOKENS", "1600")
)
GROQ_RATE_LIMIT_RETRIES = int(
    os.getenv("GROQ_RATE_LIMIT_RETRIES", "10")
)
GROQ_VISION_MAX_COMPLETION_TOKENS = int(
    os.getenv("GROQ_VISION_MAX_COMPLETION_TOKENS", "1800")
)

# Your project already imports:
# accounts.models.Branch, Student
# course.models.Axis

# إعادة المحاولة إذا قرأ النموذج الصورة لكن فشل فقط في تكوين JSON صالح.
GROQ_VISION_JSON_RETRIES = 3
