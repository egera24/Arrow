from app.config import get_settings
from app.models import TicketClassification, TicketInput
from app.providers.base import LLMProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.mock_provider import MockProvider


async def classify_ticket(provider: LLMProvider, ticket: TicketInput) -> tuple[TicketClassification, str]:
    """Classify a ticket; fall back to mock heuristics when Gemini is unavailable."""
    try:
        classification = await provider.classify_ticket(ticket)
        return classification, provider.name
    except ProviderUnavailableError:
        settings = get_settings()
        if not settings.auto_fallback_to_mock:
            raise
        mock = MockProvider()
        classification = await mock.classify_ticket(ticket)
        return classification, mock.name
