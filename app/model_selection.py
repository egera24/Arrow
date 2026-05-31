"""Gemini model selection helpers."""

from enum import Enum

SUPPORTED_GEMINI_MODELS: tuple[str, ...] = (
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
)


class GeminiModel(str, Enum):
    GEMINI_2_0_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_PRO = "gemini-1.5-pro"


MODEL_SELECTION_HINT = (
    "Set AI_MODEL in .env for the default, or pick a model from the query dropdown on classify/batch/health. "
    "Lighter models (e.g. gemini-2.0-flash-lite) often have separate free-tier quotas."
)


def resolve_model(requested: str | GeminiModel | None, default: str) -> str:
    if isinstance(requested, GeminiModel):
        requested = requested.value
    model = (requested or default).strip()
    if model not in SUPPORTED_GEMINI_MODELS:
        supported = ", ".join(SUPPORTED_GEMINI_MODELS)
        raise ValueError(f"Unsupported model '{model}'. Supported models: {supported}")
    return model
