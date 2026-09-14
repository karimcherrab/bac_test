# Add "tutor_chat" to INSTALLED_APPS.
# Keep your existing REST_FRAMEWORK / JWT authentication configuration.

import os

TUTOR_CHAT_API_KEY = os.getenv("GROQ_API_KEY", "")
TUTOR_CHAT_API_URL = "https://api.groq.com/openai/v1/chat/completions"
TUTOR_CHAT_MODEL = os.getenv("TUTOR_CHAT_MODEL", "openai/gpt-oss-120b")
TUTOR_CHAT_TIMEOUT = int(os.getenv("TUTOR_CHAT_TIMEOUT", "75"))
