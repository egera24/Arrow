import json
import re

from google import genai
from google.genai import errors as genai_errors

from app.models import TicketClassification, TicketInput, TrendReport
from app.providers.errors import ProviderUnavailableError

CLASSIFY_PROMPT = """You are a support analytics engine. Classify the ticket.

Ticket ID: {ticket_id}
Subject: {subject}
Description: {description}
Created at: {created_at}

Respond with JSON matching this schema:
{{
  "category": "billing|technical|account|shipping|other",
  "priority": "low|medium|high|critical",
  "sentiment": "positive|neutral|negative",
  "summary": "one sentence summary",
  "suggested_tags": ["tag1", "tag2"],
  "rationale": "brief explanation"
}}
"""

TREND_PROMPT = """You are a support analytics engine. Analyze classified tickets and identify themes, volume patterns, and anomalies.

Classified tickets:
{classifications}
"""


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _raise_if_api_error(exc: genai_errors.ClientError) -> None:
    code = exc.code
    if code in (401, 403, 429):
        short = "quota exceeded" if code == 429 else "authentication failed"
        raise ProviderUnavailableError(
            f"Gemini API unavailable ({code} {short}). "
            "Set DEMO_MODE=true or wait for quota reset.",
            status_code=503,
        ) from exc


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.model_name = model
        self._client = genai.Client(api_key=api_key)

    async def _generate_json(self, prompt: str) -> dict:
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                },
            )
        except genai_errors.ClientError as exc:
            _raise_if_api_error(exc)
            raise
        return _extract_json(response.text or "{}")

    async def classify_ticket(self, ticket: TicketInput) -> TicketClassification:
        prompt = CLASSIFY_PROMPT.format(
            ticket_id=ticket.ticket_id,
            subject=ticket.subject,
            description=ticket.description,
            created_at=ticket.created_at.isoformat() if ticket.created_at else "unknown",
        )
        for attempt in range(2):
            try:
                payload = await self._generate_json(prompt)
                return TicketClassification(
                    ticket_id=ticket.ticket_id,
                    category=payload["category"],
                    priority=payload["priority"],
                    sentiment=payload["sentiment"],
                    summary=payload["summary"],
                    suggested_tags=payload.get("suggested_tags", []),
                    rationale=payload.get("rationale", ""),
                )
            except (KeyError, json.JSONDecodeError, TypeError, ValueError):
                if attempt == 1:
                    raise
        raise RuntimeError("Unable to parse Gemini classification response.")

    async def analyze_trends(self, classifications: list[TicketClassification]) -> TrendReport:
        serialized = json.dumps([item.model_dump() for item in classifications], indent=2)
        prompt = TREND_PROMPT.format(classifications=serialized)
        payload = await self._generate_json(prompt)
        return TrendReport.model_validate(payload)

    async def ping(self) -> tuple[bool, str | None]:
        try:
            await self._generate_json('Respond with JSON: {"status":"ok"}')
            return True, None
        except ProviderUnavailableError as exc:
            return False, str(exc)
        except genai_errors.ClientError as exc:
            return False, f"Gemini API error ({exc.code} {exc.status})."
        except (genai_errors.APIError, RuntimeError, json.JSONDecodeError, ValueError) as exc:
            return False, f"Provider ping failed: {exc}"
