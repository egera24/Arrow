from collections import Counter

from app.config import get_settings
from app.models import BatchAnalyzeResponse, TicketClassification, TicketInput, TrendInsight, TrendReport
from app.providers.base import LLMProvider
from app.providers.errors import ProviderUnavailableError
from app.providers.mock_provider import MockProvider
from app.services.classifier import classify_ticket


def _fallback_trends(classifications: list[TicketClassification]) -> TrendReport:
    category_counts = dict(Counter(item.category for item in classifications))
    priority_counts = dict(Counter(item.priority for item in classifications))
    top_category = max(category_counts, key=category_counts.get) if category_counts else "other"
    return TrendReport(
        total_tickets=len(classifications),
        category_counts=category_counts,
        priority_counts=priority_counts,
        top_themes=[top_category],
        insights=[
            TrendInsight(
                title="Batch processed",
                detail=f"Classified {len(classifications)} tickets.",
                severity="info",
            )
        ],
        anomaly_flags=[],
    )


async def analyze_batch(
    provider: LLMProvider,
    tickets: list[TicketInput],
    *,
    limit: int,
    model: str,
    allow_mock_fallback: bool = True,
) -> BatchAnalyzeResponse:
    truncated = len(tickets) > limit
    selected = tickets[:limit]

    classifications: list[TicketClassification] = []
    provider_used = provider.name
    for ticket in selected:
        classification, used = await classify_ticket(
            provider,
            ticket,
            allow_mock_fallback=allow_mock_fallback,
        )
        classifications.append(classification)
        if used == "mock":
            provider_used = "mock"

    try:
        trends = await provider.analyze_trends(classifications)
    except ProviderUnavailableError:
        if allow_mock_fallback and get_settings().auto_fallback_to_mock:
            trends = await MockProvider().analyze_trends(classifications)
            provider_used = "mock"
        else:
            trends = _fallback_trends(classifications)
    except Exception:
        trends = _fallback_trends(classifications)

    return BatchAnalyzeResponse(
        classifications=classifications,
        trends=trends,
        provider=provider_used,
        model=model,
        demo_mode=provider_used == "mock",
        tickets_processed=len(selected),
        tickets_truncated=truncated,
    )
