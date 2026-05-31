from app.models import (
    Category,
    Priority,
    Sentiment,
    TicketClassification,
    TicketInput,
    TrendInsight,
    TrendReport,
)


def _keyword_category(subject: str, description: str) -> Category:
    text = f"{subject} {description}".lower()
    if any(word in text for word in ("invoice", "billing", "payment", "charge", "refund")):
        return "billing"
    if any(word in text for word in ("login", "password", "account", "profile", "access")):
        return "account"
    if any(word in text for word in ("ship", "delivery", "tracking", "package")):
        return "shipping"
    if any(word in text for word in ("error", "bug", "crash", "api", "integration", "timeout")):
        return "technical"
    return "other"


def _keyword_priority(subject: str, description: str) -> Priority:
    text = f"{subject} {description}".lower()
    if any(word in text for word in ("urgent", "critical", "down", "outage", "cannot work")):
        return "critical"
    if any(word in text for word in ("asap", "blocked", "failed", "immediately")):
        return "high"
    if any(word in text for word in ("question", "how to", "info")):
        return "low"
    return "medium"


def _keyword_sentiment(description: str) -> Sentiment:
    text = description.lower()
    if any(word in text for word in ("thank", "great", "appreciate", "happy")):
        return "positive"
    if any(word in text for word in ("frustrated", "angry", "unacceptable", "terrible", "urgent")):
        return "negative"
    return "neutral"


class MockProvider:
    name = "mock"

    async def classify_ticket(self, ticket: TicketInput) -> TicketClassification:
        category = _keyword_category(ticket.subject, ticket.description)
        priority = _keyword_priority(ticket.subject, ticket.description)
        sentiment = _keyword_sentiment(ticket.description)
        tags = sorted({category, priority, "demo-mode"})
        return TicketClassification(
            ticket_id=ticket.ticket_id,
            category=category,
            priority=priority,
            sentiment=sentiment,
            summary=f"{ticket.subject}: {ticket.description[:120]}".strip(),
            suggested_tags=tags,
            rationale="Demo mode response generated from keyword heuristics.",
        )

    async def analyze_trends(self, classifications: list[TicketClassification]) -> TrendReport:
        category_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}
        for item in classifications:
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
            priority_counts[item.priority] = priority_counts.get(item.priority, 0) + 1

        top_category = max(category_counts, key=category_counts.get) if category_counts else "other"
        insights = [
            TrendInsight(
                title="Top category",
                detail=f"'{top_category}' is the most common category in this batch.",
                severity="info",
            ),
            TrendInsight(
                title="Priority mix",
                detail=f"High/critical tickets: {priority_counts.get('high', 0) + priority_counts.get('critical', 0)}.",
                severity="warning" if priority_counts.get("critical", 0) else "info",
            ),
        ]
        anomalies: list[str] = []
        if category_counts.get(top_category, 0) >= max(3, len(classifications) // 2):
            anomalies.append(f"Spike detected in '{top_category}' tickets.")

        return TrendReport(
            total_tickets=len(classifications),
            category_counts=category_counts,
            priority_counts=priority_counts,
            top_themes=[top_category],
            insights=insights,
            anomaly_flags=anomalies,
        )

    async def ping(self) -> tuple[bool, str | None]:
        return True, None
