from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


Category = Literal["billing", "technical", "account", "shipping", "other"]
Priority = Literal["low", "medium", "high", "critical"]
Sentiment = Literal["positive", "neutral", "negative"]

TICKET_EXAMPLE = {
    "ticket_id": "TKT-1001",
    "subject": "Cannot log in to customer portal",
    "description": "User reports login failures since this morning.",
}


class TicketInput(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [TICKET_EXAMPLE],
        }
    )

    ticket_id: str = Field(..., examples=["TKT-1001"])
    subject: str = Field(..., min_length=1, examples=["Cannot log in to portal"])
    description: str = Field(..., min_length=1, examples=["User reports login failures since this morning."])
    created_at: Annotated[datetime | None, SkipJsonSchema()] = Field(
        default=None,
        description="Optional ISO datetime, e.g. 2026-05-28T09:15:00. Omit this field if unknown.",
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def ignore_swagger_placeholder(cls, value: object) -> object | None:
        if value == "string":
            return None
        return value


class TicketClassification(BaseModel):
    ticket_id: str
    category: Category
    priority: Priority
    sentiment: Sentiment
    summary: str
    suggested_tags: list[str]
    rationale: str


class ClassifyResponse(BaseModel):
    ticket_id: str
    classification: TicketClassification
    provider: str
    model: str
    demo_mode: bool = False


class BatchAnalyzeJsonRequest(BaseModel):
    tickets: list[TicketInput]


class TrendInsight(BaseModel):
    title: str
    detail: str
    severity: Literal["info", "warning", "critical"]


class TrendReport(BaseModel):
    total_tickets: int
    category_counts: dict[str, int]
    priority_counts: dict[str, int]
    top_themes: list[str]
    insights: list[TrendInsight]
    anomaly_flags: list[str]


class BatchAnalyzeResponse(BaseModel):
    classifications: list[TicketClassification]
    trends: TrendReport
    provider: str
    model: str
    demo_mode: bool = False
    tickets_processed: int
    tickets_truncated: bool = False


class ModelsResponse(BaseModel):
    default_model: str
    supported_models: list[str]
    hint: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    provider: str
    api_key_configured: bool
    demo_mode: bool
    model: str
    provider_reachable: bool | None = None
    message: str | None = None
