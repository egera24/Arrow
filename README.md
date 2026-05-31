# Support Ticket Intelligence API

A Python FastAPI service that classifies support tickets and generates batch trend insights using an AI model (Google Gemini by default). Built as an interview demo for a **Data & Automation Engineer** role — it mirrors ticket classification, automated insights, and export paths toward BI tools like Power BI.

## What it does

- **Single ticket classification** — unstructured ticket text → structured fields (category, priority, sentiment, summary, tags)
- **Batch analysis** — process a CSV or JSON array of tickets and return per-ticket classifications plus trend insights and anomaly flags
- **CSV export** — download the last batch result for Power BI or Excel
- **Live demo ready** — Swagger UI at `/docs` for real-time requests during interviews

## Quick start

### 1. Create a virtual environment

```powershell
cd "c:\Python Projects\Arrow"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment

Copy the example env file and add your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey):

```powershell
copy .env.example .env
```

Edit `.env`:

```env
AI_PROVIDER=gemini
AI_API_KEY=your_key_here
AI_MODEL=gemini-2.0-flash
DEMO_MODE=false
```

> **Never commit `.env` or share your API key.** If a key was exposed, revoke it and create a new one.

### 3. Run the server

**Important:** use the project virtual environment. If you run `uvicorn` without activating `.venv`, you may get `ModuleNotFoundError: No module named 'pydantic_settings'`.

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the helper script (no activation needed):

```powershell
.\run.ps1
```

Or call uvicorn directly from the venv:

```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for interactive API documentation.

### 4. Demo without an API key

Set `DEMO_MODE=true` in `.env` to use keyword-based mock responses (useful for offline testing).

### 5. Choose a Gemini model

Free-tier quotas are **per model**. If `gemini-2.0-flash` hits rate limits, switch models:

**Default (`.env`):**

```env
AI_MODEL=gemini-2.0-flash-lite
```

**Per request (Swagger query param `model` or curl):**

```powershell
curl "http://localhost:8000/tickets/classify?model=gemini-2.5-flash-lite" `
  -H "Content-Type: application/json" `
  -d "{\"ticket_id\":\"TKT-1001\",\"subject\":\"Cannot log in\",\"description\":\"Login failed.\"}"
```

List supported models: **GET `/models`**. Test connectivity for a model: **GET `/health?model=gemini-2.5-flash-lite`**.

Supported IDs include: `gemini-2.0-flash-lite`, `gemini-2.0-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/models` | List supported Gemini models and default |
| GET | `/health` | Readiness check (optional `?model=` to ping a specific model) |
| POST | `/tickets/classify` | Classify a single ticket |
| POST | `/tickets/analyze-batch` | Analyze a JSON array of tickets |
| POST | `/tickets/analyze-batch/upload` | Upload CSV file for batch analysis |
| GET | `/tickets/export` | Download last batch classifications as CSV |

## Example requests

### Classify one ticket

```powershell
curl -X POST "http://localhost:8000/tickets/classify" `
  -H "Content-Type: application/json" `
  -d "{\"ticket_id\":\"TKT-1001\",\"subject\":\"Cannot log in\",\"description\":\"User reports login failures since this morning.\"}"
```

### Analyze batch (JSON)

```powershell
curl -X POST "http://localhost:8000/tickets/analyze-batch" `
  -H "Content-Type: application/json" `
  -d @batch.json
```

### Analyze batch (CSV upload)

Use Swagger UI at `/docs` → **POST /tickets/analyze-batch/upload** → upload `data/sample_tickets.csv`.

Or with curl:

```powershell
curl -X POST "http://localhost:8000/tickets/analyze-batch/upload" `
  -F "file=@data/sample_tickets.csv"
```

### Export for Power BI

After running a batch analysis:

```powershell
curl -O -J "http://localhost:8000/tickets/export"
```

This CSV maps directly to a Power BI dataset for trend dashboards.

## Interview demo script (~5 minutes)

1. **Problem** — Support teams need automated classification before data reaches BI.
2. **Health check** — `GET /health` to confirm the service and provider are ready.
3. **Live classify** — Submit a custom ticket in Swagger; show structured JSON output.
4. **Batch analysis** — Upload `data/sample_tickets.csv`; highlight login-failure cluster and billing themes.
5. **Export** — `GET /tickets/export` and mention Power BI ingestion.
6. **Architecture** — Provider adapter, Pydantic schemas, env-based config, production path: ticketing webhook → pipeline → warehouse → Power BI.

## Pre-interview checklist

- [ ] Server running; `/health` returns `ok`
- [ ] One live classify request succeeds
- [ ] Batch upload on `data/sample_tickets.csv` completes within ~30 seconds
- [ ] `DEMO_MODE=false` for the live portion
- [ ] API key credits confirmed at [Google AI Studio](https://aistudio.google.com/)

## Project structure

```
app/
  main.py              # FastAPI routes
  models.py            # Request/response schemas
  config.py            # Environment settings
  state.py             # Last batch result + CSV helpers
  providers/           # AI provider adapter (Gemini + mock)
  services/            # Classification and batch logic
data/
  sample_tickets.csv   # Demo dataset
tests/
  test_api.py          # API tests (demo mode)
```

## Run tests

```powershell
pytest
```

## Production roadmap

- Ingest tickets from Salesforce / support platform webhooks
- Stage raw + enriched data in SQL warehouse
- Schedule Power BI dataset refresh
- Add auth, rate limiting, and observability

## License

Demo project for interview purposes.
