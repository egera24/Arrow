from app.config import Settings, get_settings
from app.providers.base import LLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.mock_provider import MockProvider


def get_provider(settings: Settings | None = None, *, model: str | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.demo_mode or not settings.ai_api_key:
        return MockProvider()
    if settings.ai_provider.lower() == "gemini":
        effective_model = model or settings.ai_model
        return GeminiProvider(api_key=settings.ai_api_key, model=effective_model)
    raise ValueError(
        f"Unsupported AI provider '{settings.ai_provider}'. "
        "Set AI_PROVIDER=gemini or enable DEMO_MODE=true."
    )
