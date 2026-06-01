# Support Ticket Intelligence API — Demo Preparation Guide

Use this as your personal cheat sheet for the interview demo. It reflects how the application works **today** in your codebase.

---

## 1. Elevator pitch (30 seconds)

**Problem:** Support teams receive unstructured tickets (email, portal, chat). Before analytics in Power BI, someone must read each ticket and label category, priority, sentiment, etc.

**Solution:** This API automates that enrichment step. Raw ticket text goes in → structured JSON (and CSV for BI) comes out. It is built as a **Data & Automation Engineer** demo: ingest → classify/enrich → batch insights → export → dashboard.

**One-liner:** *“A FastAPI microservice that turns support tickets into structured data using Gemini, with a mock path for offline demos and a CSV export path into Power BI.”*

---

## 2. Technology stack

| Layer | Technology | Role in this project |
|--------|------------|---------------------|
| **Language** | Python 3.12 | Application runtime (Docker base image) |
| **Web framework** | FastAPI 0.136 | REST API, OpenAPI/Swagger at `/docs`, async routes |
| **ASGI server** | Uvicorn 0.48 | Local dev (`run.ps1`) and production (Docker/Render) |
| **Validation / schemas** | Pydantic v2 | Request/response models, enum constraints, Swagger examples |
| **Configuration** | pydantic-settings | Loads `.env` locally; Render uses OS env vars |
| **AI provider** | Google Gemini via `google-genai` 2.7 | Live classification and trend analysis (JSON mode) |
| **HTTP client (tests)** | httpx | Async API tests |
| **Testing** | pytest + pytest-asyncio | 17 API tests, no live Gemini in CI |
| **File upload** | python-multipart | CSV batch upload endpoint |
| **Containerization** | Docker | Production image for Render |
| **Cloud hosting** | Render (free tier) | Public HTTPS URL, auto-deploy from GitHub |
| **CI** | GitHub Actions | Runs `pytest -q` on push/PR |

**Not in stack (by design):** database, message queue, auth, persistent storage — intentional for a focused demo; production roadmap mentions warehouse + webhooks.

---

## 3. Application logic (end-to-end)

### High-level pipeline

```
Client (Swagger / curl / future webhook)
    ↓
FastAPI route (main.py)
    ↓
Validate input (Pydantic models)
    ↓
Resolve settings (config.py): API key, model, demo mode, batch limit
    ↓
Choose provider (factory.py): Gemini OR Mock
    ↓
Service layer (classifier.py / batch_analyzer.py)
    ↓
Provider (gemini_provider.py OR mock_provider.py)
    ↓
Structured response (models.py)
    ↓
(Optional) Store last batch in memory (state.py) → CSV export
```

### Provider selection logic

The app always picks **one** of two backends:

| Condition | Provider used |
|-----------|----------------|
| `?demo_mode=true` | Mock (keyword heuristics) |
| `?demo_mode=false` + valid API key | Gemini |
| `DEMO_MODE=true` in env (no query override) | Mock |
| No API key configured | Mock (default) or 503 if `?demo_mode=false` explicitly |
| Gemini fails (429/auth) + fallback allowed | Mock (silent fallback) |
| Gemini fails + `?demo_mode=false` explicitly | **503** with error (includes model name) |

### What Gemini receives (single classify)

One text prompt containing:

- Role: *“You are a support analytics engine”*
- Ticket: `ticket_id`, `subject`, `description`, `created_at` (or `"unknown"`)
- Instructions to return JSON: `category`, `priority`, `sentiment`, `summary`, `suggested_tags`, `rationale`

Settings: `temperature=0.2`, `response_mime_type=application/json`.

**No** company rules, few-shot examples, or customer history — general model reasoning only.

### Batch flow

1. Accept tickets (JSON array or CSV upload).
2. Truncate to `BATCH_SIZE_LIMIT` (default 10).
3. Classify each ticket (same path as single classify).
4. Send all classifications to Gemini again for **trend analysis** (themes, counts, insights, anomaly flags).
5. Store full batch result in **memory** for export.
6. Return classifications + trends in one JSON response.

### Export flow

- **Only batch endpoints** write to memory (`set_last_batch_result`).
- **Single classify does NOT** feed export.
- `GET /tickets/export` converts last batch classifications to CSV.
- Data is **in-memory only** — lost on server restart or Render cold start.

---

## 4. Module-by-module reference

### `app/main.py` — HTTP layer & orchestration

**Goal:** Define all routes, wire dependencies, handle errors, customize OpenAPI.

**Responsibilities:**

- Routes: `/`, `/models`, `/health`, `/health/live`, classify, batch (JSON + CSV), export
- Query params: `?model=`, `?demo_mode=`
- Exception handlers: validation hints (Swagger pitfalls), `ProviderUnavailableError` → 503
- Custom OpenAPI: hides misleading 422 docs
- Redirects `/` → `/docs`

**Demo talking point:** *“Thin controller layer — routes delegate to services and providers.”*

---

### `app/models.py` — Data contracts

**Goal:** Strict schemas for API input/output and Swagger documentation.

**Key types:**

| Model | Purpose |
|-------|---------|
| `TicketInput` | Incoming ticket: id, subject, description, optional `created_at` |
| `TicketClassification` | Enriched output: category, priority, sentiment, summary, tags, rationale |
| `ClassifyResponse` | Single ticket result + metadata (`provider`, `model`, `demo_mode`) |
| `BatchAnalyzeResponse` | Classifications + trends + batch metadata |
| `TrendReport` | Aggregates: counts, themes, insights, anomaly flags |
| `HealthResponse` | Service/provider readiness |
| `ModelsResponse` | Supported Gemini models list |

**Enums:** `category` (billing, technical, account, shipping, other), `priority` (low → critical), `sentiment` (positive, neutral, negative).

**Demo talking point:** *“Pydantic ensures BI-ready structured output, not free-form text.”*

---

### `app/config.py` — Environment configuration

**Goal:** Centralize settings from `.env` / Render env vars.

**Settings:**

- `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`
- `DEMO_MODE`, `AUTO_FALLBACK_TO_MOCK`, `BATCH_SIZE_LIMIT`

**Note:** `get_settings()` is cached — restart server after `.env` changes.

---

### `app/model_selection.py` — Gemini model helpers

**Goal:** Validate and resolve which Gemini model to use.

- Hardcoded list of 6 supported models
- `GeminiModel` enum for Swagger dropdown
- `resolve_model()`: query param overrides `AI_MODEL` from env

**Demo talking point:** *“Free-tier quotas are per model — we can switch models per request without redeploying.”*

---

### `app/providers/factory.py` — Provider factory

**Goal:** Single place to choose Mock vs Gemini.

- `resolve_demo_mode()`: query param overrides env; no key → demo default
- `get_provider()`: returns `MockProvider` or `GeminiProvider(api_key, model)`

**Demo talking point:** *“Adapter pattern — swap AI vendor without changing routes or services.”*

---

### `app/providers/gemini_provider.py` — Live AI backend

**Goal:** Call Google Gemini for classification and trend analysis.

- Builds prompts, calls `generate_content` in JSON mode
- Maps Gemini JSON → `TicketClassification` / `TrendReport`
- `ping()` for `/health` connectivity check
- Errors 401/403/429 → `ProviderUnavailableError` with **model name** in message

---

### `app/providers/mock_provider.py` — Demo / offline backend

**Goal:** Keyword-based classifications when Gemini unavailable or demo mode requested.

- Category/priority/sentiment from simple word matching
- Tags include `"demo-mode"`
- No external API calls — fast, reliable for interviews

---

### `app/providers/base.py` — Provider interface

**Goal:** Abstract contract (`classify_ticket`, `analyze_trends`, `ping`) so Gemini and Mock are interchangeable.

---

### `app/providers/errors.py` — Provider errors

**Goal:** `ProviderUnavailableError` with HTTP status (503) for quota/auth failures.

---

### `app/services/classifier.py` — Classification service

**Goal:** Orchestrate one ticket classification with optional fallback.

- Calls provider’s `classify_ticket`
- On `ProviderUnavailableError`: fallback to mock **unless** `?demo_mode=false` explicitly (`allow_mock_fallback=False`)

---

### `app/services/batch_analyzer.py` — Batch service

**Goal:** Process many tickets + aggregate trends.

- Loops tickets through classifier
- Calls provider’s `analyze_trends` on full classification set
- Fallback trend report if Gemini trend step fails
- Respects batch size limit and `allow_mock_fallback`

---

### `app/state.py` — In-memory session state

**Goal:** Hold last batch result for CSV export; parse uploaded CSV.

- `_last_batch_result`: global in-memory variable (one batch only)
- `parse_tickets_csv()`: CSV → list of `TicketInput`
- `batch_result_to_csv()`: classifications → downloadable CSV

**Demo caveat:** *“Export works in the same session; cold start clears it — in production we’d persist to a warehouse.”*

---

### `data/sample_tickets.csv` — Demo dataset

**Goal:** 20 realistic tickets for batch demo (login cluster, billing, shipping, technical, low-priority questions).

---

### `tests/test_api.py` — Automated tests

**Goal:** Regression safety without live Gemini (17 tests, `DEMO_MODE=true`, empty key).

Covers: health, classify, batch, export, model override, demo mode query, no-fallback on explicit live mode.

---

### Infrastructure files

| File | Goal |
|------|------|
| `Dockerfile` | Production container: Python 3.12, install deps, run uvicorn on `$PORT` |
| `render.yaml` | Render Blueprint: env vars, health check `/health/live` |
| `.github/workflows/ci.yml` | CI pytest on push/PR |
| `run.ps1` | One-command local start from `.venv` |
| `.env.example` | Committed config template (no secrets) |

---

## 5. API functionalities & goals

| Endpoint | Method | Goal | Demo use |
|----------|--------|------|----------|
| `/` | GET | Redirect to Swagger | Entry point |
| `/docs` | GET | Interactive API docs | **Main demo UI** |
| `/models` | GET | List supported Gemini models + default | Show model flexibility |
| `/health/live` | GET | Fast liveness (no Gemini) | Render health checks |
| `/health` | GET | Full readiness + optional Gemini ping | Open demo: “service is up” |
| `/tickets/classify` | POST | Enrich **one** ticket | Live AI moment: custom ticket |
| `/tickets/analyze-batch` | POST | Classify JSON ticket list + trends | Programmatic batch |
| `/tickets/analyze-batch/upload` | POST | Classify CSV + trends | **Upload `sample_tickets.csv`** |
| `/tickets/export` | GET | Download last batch as CSV | **Power BI story** |

### Query parameters (classify / batch / health)

| Param | Goal |
|-------|------|
| `model` | Override Gemini model for this request |
| `demo_mode` | `true` = mock, `false` = live (no silent fallback), omit = env default |

---

## 6. Classification output fields (what to explain)

| Field | Meaning | Business value |
|-------|---------|----------------|
| **category** | Issue type (billing, account, …) | Routing, queue assignment |
| **priority** | Urgency (low → critical) | SLA, escalation |
| **sentiment** | Customer tone (positive/neutral/negative) | CSAT risk, coaching |
| **summary** | One-sentence recap | Agent skim, dashboards |
| **suggested_tags** | Extra labels | Search, filtering in BI |
| **rationale** | Why the model chose those labels | Transparency, trust, tuning |

Trend batch adds: **category_counts**, **priority_counts**, **top_themes**, **insights**, **anomaly_flags** (e.g. login spike).

---

## 7. Environment variables (talking points)

| Variable | Purpose |
|----------|---------|
| `AI_API_KEY` | Gemini authentication (secret) |
| `AI_MODEL` | Default model when query param omitted |
| `DEMO_MODE` | Global default: mock vs live |
| `AUTO_FALLBACK_TO_MOCK` | On Gemini failure, return mock (200) vs 503 |
| `BATCH_SIZE_LIMIT` | Max tickets per batch (keeps demo fast) |

---

## 8. Suggested 5-minute demo script

1. **Problem (30 s)** — Unstructured tickets block analytics; need automated enrichment before Power BI.

2. **Health (30 s)** — `GET /health` → status, provider, model. Mention `/health/live` for Render.

3. **Live classify (1 min)** — Custom ticket in Swagger, `demo_mode=false`, show JSON: category, priority, sentiment, rationale. Explain prompt-based AI (no training yet).

4. **Batch (1.5 min)** — Upload `data/sample_tickets.csv`. Highlight login-failure cluster, billing themes, anomaly flags in trends.

5. **Export (45 s)** — `GET /tickets/export` → CSV columns → *“This feeds Power BI for trend dashboards.”*

6. **Architecture (1 min)** — Provider adapter, Pydantic schemas, env config, demo mode for interviews. **Production path:** Salesforce/webhook → API → SQL warehouse → scheduled Power BI refresh.

---

## 9. Pre-demo checklist

- [ ] Server running (`.\run.ps1` or Render URL)
- [ ] Wake Render with `/health/live` if cold start
- [ ] Disable ad blocker for Render domain (Swagger fetch issues)
- [ ] `/health` returns ok or degraded (know your quota status)
- [ ] Have `sample_tickets.csv` ready
- [ ] Run batch **then** export in same session
- [ ] If quota exhausted: use `?demo_mode=true` or `?model=gemini-2.5-flash-lite`
- [ ] Know difference: single classify ≠ export; batch required for export

---

## 10. Likely interview questions & answers

**Why no database?**  
Demo scope — in-memory export proves the BI handoff pattern; production would use a warehouse.

**How would you improve classification accuracy?**  
Prompt rubric + few-shot examples first; then human feedback loop storing corrections; fine-tuning or RAG at scale.

**What if Gemini is down?**  
Mock fallback (default), or 503 when user explicitly requests live mode.

**How is this a Data & Automation role fit?**  
Automates manual ticket tagging, produces structured datasets, batch trends, CSV export to Power BI — classic ETL/enrichment pipeline shape.

**Security concerns?**  
Public Swagger on free Render consumes API quota; production needs auth, rate limits, secret management.

---

## 11. Production roadmap (from README — good closing slide)

1. Webhook ingest from Salesforce / Zendesk  
2. Persist raw + enriched data in SQL warehouse  
3. Scheduled Power BI dataset refresh  
4. Auth, rate limiting, observability  

---

## 12. Quick reference URLs

- **Local Swagger:** http://localhost:8000/docs  
- **Cloud (if deployed):** https://arrow-2mz5.onrender.com/docs  
- **Demo file:** `data/sample_tickets.csv` (20 tickets)

---

You can copy this document into your notes app or print it for the interview. No code changes were made to the repository.