from typing import Protocol

from app.models import TicketClassification, TicketInput, TrendReport


class LLMProvider(Protocol):
    name: str

    async def classify_ticket(self, ticket: TicketInput) -> TicketClassification: ...

    async def analyze_trends(self, classifications: list[TicketClassification]) -> TrendReport: ...

    async def ping(self) -> tuple[bool, str | None]: ...
