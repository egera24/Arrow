import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["DEMO_MODE"] = "true"
os.environ["AI_API_KEY"] = ""

from app.main import app
from app.providers.errors import ProviderUnavailableError


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_ok_in_demo_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["demo_mode"] is True


@pytest.mark.asyncio
async def test_health_shows_specific_ping_failure():
    gemini_provider = AsyncMock()
    gemini_provider.name = "gemini"
    gemini_provider.ping = AsyncMock(
        return_value=(False, "Gemini API unavailable (429 quota exceeded). Set DEMO_MODE=true or wait for quota reset.")
    )
    with patch("app.main.get_settings") as mock_settings, patch("app.main.get_provider", return_value=gemini_provider):
        mock_settings.return_value.demo_mode = False
        mock_settings.return_value.ai_api_key = "test-key"
        mock_settings.return_value.ai_model = "gemini-2.0-flash"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert "429 quota exceeded" in payload["message"]
    assert payload["provider_reachable"] is False


@pytest.mark.asyncio
async def test_list_models():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/models")
    assert response.status_code == 200
    payload = response.json()
    assert "gemini-2.5-flash" in payload["supported_models"]
    assert payload["default_model"]


@pytest.mark.asyncio
async def test_classify_rejects_unknown_model():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tickets/classify?model=gemini-9.9-ultra",
            json={
                "ticket_id": "TKT-BAD-MODEL",
                "subject": "Cannot log in",
                "description": "User cannot access account.",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_openapi_hides_422_validation_docs():
    schema = app.openapi()
    classify_responses = schema["paths"]["/tickets/classify"]["post"]["responses"]
    assert "422" not in classify_responses
    gemini_model_schema = schema["components"]["schemas"]["GeminiModel"]
    assert "enum" in gemini_model_schema
    ticket_input = schema["components"]["schemas"]["TicketInput"]
    assert "created_at" not in ticket_input.get("properties", {})


@pytest.mark.asyncio
async def test_classify_passes_model_override_to_provider():
    with patch("app.main.get_provider") as mock_get_provider:
        from app.providers.mock_provider import MockProvider

        mock_get_provider.return_value = MockProvider()
        with patch("app.main.get_settings") as mock_settings:
            mock_settings.return_value.demo_mode = False
            mock_settings.return_value.ai_api_key = "test-key"
            mock_settings.return_value.ai_model = "gemini-2.0-flash"
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/tickets/classify?model=gemini-2.5-flash-lite",
                    json={
                        "ticket_id": "TKT-MODEL",
                        "subject": "Cannot log in",
                        "description": "User cannot access account.",
                    },
                )
    assert response.status_code == 200
    assert response.json()["model"] == "gemini-2.5-flash-lite"
    mock_get_provider.assert_called_once_with(mock_settings.return_value, model="gemini-2.5-flash-lite")


@pytest.mark.asyncio
async def test_classify_ticket():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tickets/classify",
            json={
                "ticket_id": "TKT-TEST-1",
                "subject": "Cannot log in",
                "description": "User cannot access account after password reset.",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["category"] == "account"
    assert payload["demo_mode"] is True


@pytest.mark.asyncio
async def test_classify_ignores_swagger_created_at_placeholder():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tickets/classify",
            json={
                "ticket_id": "TKT-TEST-2",
                "subject": "Cannot log in",
                "description": "User cannot access account.",
                "created_at": "string",
            },
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_classify_falls_back_when_gemini_unavailable():
    gemini_provider = AsyncMock()
    gemini_provider.name = "gemini"
    gemini_provider.classify_ticket = AsyncMock(
        side_effect=ProviderUnavailableError("Gemini quota exceeded", status_code=503)
    )
    with patch("app.main.get_provider", return_value=gemini_provider):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/tickets/classify",
                json={
                    "ticket_id": "TKT-FALLBACK",
                    "subject": "Cannot log in",
                    "description": "User cannot access account after password reset.",
                },
            )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["demo_mode"] is True
    assert payload["classification"]["category"] == "account"


@pytest.mark.asyncio
async def test_analyze_batch_json():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tickets/analyze-batch",
            json={
                "tickets": [
                    {
                        "ticket_id": "TKT-1",
                        "subject": "Invoice duplicate charge",
                        "description": "Customer billed twice on latest invoice.",
                    },
                    {
                        "ticket_id": "TKT-2",
                        "subject": "API timeout",
                        "description": "Integration requests fail with timeout errors.",
                    },
                ]
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tickets_processed"] == 2
    assert len(payload["classifications"]) == 2
    assert payload["trends"]["total_tickets"] == 2


@pytest.mark.asyncio
async def test_analyze_batch_csv_upload():
    csv_content = (
        "ticket_id,subject,description,created_at\n"
        "TKT-9,Billing issue,Unexpected charge on invoice,2026-05-28T10:00:00\n"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tickets/analyze-batch/upload",
            files={"file": ("tickets.csv", csv_content, "text/csv")},
        )
    assert response.status_code == 200
    assert response.json()["tickets_processed"] == 1


@pytest.mark.asyncio
async def test_export_after_batch():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/tickets/analyze-batch",
            json={
                "tickets": [
                    {
                        "ticket_id": "TKT-EXP",
                        "subject": "Shipping delay",
                        "description": "Package has not moved in 5 days.",
                    }
                ]
            },
        )
        export_response = await client.get("/tickets/export")
    assert export_response.status_code == 200
    assert "ticket_id" in export_response.text
    assert "TKT-EXP" in export_response.text
