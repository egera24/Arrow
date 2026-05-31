# Support Ticket Intelligence API

A Python FastAPI service that classifies support tickets and generates batch trend insights using an AI model (Google Gemini by default). Built as an interview demo for a **Data & Automation Engineer** role — it mirrors ticket classification, automated insights, and export paths toward BI tools like Power BI.

## What it does

- **Single ticket classification** — unstructured ticket text → structured fields (category, priority, sentiment, summary, tags)
- **Batch analysis** — process a CSV or JSON array of tickets and return per-ticket classifications plus trend insights and anomaly flags
- **CSV export** — download the last batch result for Power BI or Excel
- **Live demo ready** — Swagger UI at `/docs` for real-time requests during interviews
- **Cloud deployable** — Docker + [Render](https://render.com) free tier for a public HTTPS URL (no local server required)

## Quick start (local)

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
$BASE_URL = "http://localhost:8000"  # or https://your-service.onrender.com
curl "$BASE_URL/tickets/classify?model=gemini-2.5-flash-lite" `
  -H "Content-Type: application/json" `
  -d "{\"ticket_id\":\"TKT-1001\",\"subject\":\"Cannot log in\",\"description\":\"Login failed.\"}"
```

List supported models: **GET `/models`**. Test connectivity for a model: **GET `/health?model=gemini-2.5-flash-lite`**.

Supported IDs include: `gemini-2.0-flash-lite`, `gemini-2.0-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`.

## Deploy to Render (free tier)

Host the API on the internet without running a local server. Swagger stays at `/docs` on your public URL.

### Prerequisites

1. Push this repo to GitHub
2. A [Render](https://render.com) account (free)
3. A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Steps

1. **GitHub** — create a repo and push `main`:
   ```powershell
   git remote add origin https://github.com/YOUR_USER/arrow.git
   git push -u origin main
   ```
2. **Render** — Dashboard → **New** → **Web Service** → connect your GitHub repo
3. Render detects the [`Dockerfile`](Dockerfile) automatically (runtime: Docker, plan: Free)
4. **Environment variables** — add in the Render dashboard (mirror [`.env.example`](.env.example)):
   | Key | Value |
   |-----|-------|
   | `AI_API_KEY` | Your Gemini key (mark as secret) |
   | `AI_MODEL` | `gemini-2.0-flash-lite` |
   | `DEMO_MODE` | `false` |
   | `AUTO_FALLBACK_TO_MOCK` | `true` |
   | `BATCH_SIZE_LIMIT` | `10` |
5. **Deploy** — when the build finishes, open `https://<your-service-name>.onrender.com/docs`

Alternatively, use the [`render.yaml`](render.yaml) Blueprint for one-click setup from the repo.

### Free-tier behavior

- **Cold starts** — free services sleep after ~15 minutes idle; the first request may take 30–60 seconds
- **In-memory export** — `GET /tickets/export` only works for the last batch in the current instance; after a cold start or redeploy, run batch analysis again before exporting
- **Public API** — anyone with the URL can use Swagger and consume your Gemini quota; acceptable for a demo interview project

### Verify deployment

- `GET https://<your-service>.onrender.com/health` → `ok` or `degraded` (quota)
- `GET https://<your-service>.onrender.com/docs` → Swagger UI over HTTPS
- Run batch + export in the same session before the service sleeps

### Local Docker smoke test (optional)

```powershell
docker build -t arrow-api .
docker run --rm -p 8000:8000 -e DEMO_MODE=true arrow-api
```

Open http://localhost:8000/docs

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

Set the base URL first:

```powershell
# Local
$BASE_URL = "http://localhost:8000"

# Render (replace with your service URL)
# $BASE_URL = "https://your-service-name.onrender.com"
```

### Classify one ticket

```powershell
curl -X POST "$BASE_URL/tickets/classify" `
  -H "Content-Type: application/json" `
  -d "{\"ticket_id\":\"TKT-1001\",\"subject\":\"Cannot log in\",\"description\":\"User reports login failures since this morning.\"}"
```

### Analyze batch (JSON)

```powershell
curl -X POST "$BASE_URL/tickets/analyze-batch" `
  -H "Content-Type: application/json" `
  -d @batch.json
```

### Analyze batch (CSV upload)

Use Swagger UI at `/docs` → **POST /tickets/analyze-batch/upload** → upload `data/sample_tickets.csv`.

Or with curl:

```powershell
curl -X POST "$BASE_URL/tickets/analyze-batch/upload" `
  -F "file=@data/sample_tickets.csv"
```

### Export for Power BI

After running a batch analysis:

```powershell
curl -O -J "$BASE_URL/tickets/export"
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

- [ ] API reachable at local `/docs` or Render `/docs` URL
- [ ] `/health` returns `ok`
- [ ] One live classify request succeeds
- [ ] Batch upload on `data/sample_tickets.csv` completes within ~30 seconds
- [ ] `DEMO_MODE=false` for the live portion
- [ ] API key credits confirmed at [Google AI Studio](https://aistudio.google.com/)

## Project structure

```
app/
  main.py              # FastAPI routes
  models.py            # Request/response schemas
  config.py            # Environment settings (optional .env; reads Render env vars)
  state.py             # Last batch result + CSV helpers
  providers/           # AI provider adapter (Gemini + mock)
  services/            # Classification and batch logic
data/
  sample_tickets.csv   # Demo dataset
tests/
  test_api.py          # API tests (demo mode)
Dockerfile             # Production container (Render)
render.yaml            # Render Blueprint
.github/workflows/ci.yml
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
