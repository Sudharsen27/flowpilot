from app.ai.groq_provider import GroqProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.provider import AIProvider
from app.core.config import settings


def create_ai_provider() -> AIProvider:
    """Construct the configured AIProvider. Shared by FastAPI and workers."""
    if settings.ai_provider == "groq":
        return GroqProvider()
    return OpenAIProvider()
