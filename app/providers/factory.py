from app.config import Settings, get_settings
from app.providers.base import LLMProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.gemini_provider import GeminiProvider
from app.providers.mock_provider import MockProvider

_PLACEHOLDER_API_KEY = "your_gemini_api_key_here"


def resolve_demo_mode(request_override: bool | None, settings: Settings) -> bool:
    if request_override is not None:
        return request_override
    if not _api_key_configured(settings):
        return True
    return settings.demo_mode


def _api_key_configured(settings: Settings) -> bool:
    return bool(settings.ai_api_key) and settings.ai_api_key != _PLACEHOLDER_API_KEY


def get_provider(
    settings: Settings | None = None,
    *,
    model: str | None = None,
    demo_mode: bool | None = None,
) -> LLMProvider:
    settings = settings or get_settings()
    use_mock = resolve_demo_mode(demo_mode, settings)
    if use_mock:
        return MockProvider()
    if not _api_key_configured(settings):
        raise ProviderUnavailableError(
            "Live mode requires AI_API_KEY. Use ?demo_mode=true or set DEMO_MODE=true."
        )
    if settings.ai_provider.lower() == "gemini":
        effective_model = model or settings.ai_model
        return GeminiProvider(api_key=settings.ai_api_key, model=effective_model)
    raise ValueError(
        f"Unsupported AI provider '{settings.ai_provider}'. "
        "Set AI_PROVIDER=gemini or enable DEMO_MODE=true."
    )
