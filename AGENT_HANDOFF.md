# Agent Handoff — Support Ticket Intelligence API

**Read this file first** when picking up work on this project (debugging, features, interview prep).

| | |
|---|---|
| **Workspace** | `C:\Python Projects\Arrow` |
| **Purpose** | Interview demo for a Data & Automation Engineer role |
| **Stack** | FastAPI, Pydantic v2, Google Gemini (`google-genai` SDK), pytest, Docker |
| **Git** | Local repo on `main`; push to GitHub for Render auto-deploy |
| **Cloud (live)** | https://arrow-2mz5.onrender.com — Swagger at `/docs`, root `/` redirects to `/docs` |
| **Last updated** | 2026-06-01 |

---

## What this project does

Classifies support tickets and generates batch trend insights. Designed for live Swagger demos and maps to: ticket enrichment → batch ETL → CSV export → Power BI.

- **Gemini path** — real AI when `DEMO_MODE=false` and API key is set
- **Mock path** — keyword heuristics when `DEMO_MODE=true`, no key, or auto-fallback triggers
- **Model selection** — default via `.env` / Render env vars, per-request override via `?model=` query param
- **Supported models** — hardcoded in `app/model_selection.py` (`GET /models` does not call Google API)

User-facing docs: `README.md`. Demo script and checklist are there too.

---

## Quick start (local)

```powershell
cd "C:\Python Projects\Arrow"
.\run.ps1
```

Swagger: http://localhost:8000/docs

**Always use `.venv`.** Global `uvicorn` causes `ModuleNotFoundError: No module named 'pydantic_settings'`.

```powershell
copy .env.example .env   # first time only; add AI_API_KEY
.\.venv\Scripts\pytest -q
```

**Only one server on port 8000 locally.** Multiple uvicorn instances cause confusing provider/env behavior. Check with `netstat -ano | findstr :8000`.

For cloud demos, use the Render URL above — see **Cloud deployment** below.

---

## Cloud deployment (Render)

**Live URL:** https://arrow-2mz5.onrender.com/docs

```
GitHub push → Render Docker build → HTTPS web service
  → env vars from Render dashboard (no .env file in container)
  → GET /health/live for Render platform health checks (no Gemini call)
  → GET /health for full provider ping (demo / diagnostics)
```

### Deploy steps

1. Push repo to GitHub
2. Render → New Web Service → connect repo → Docker runtime, free plan
3. Set env vars: `AI_API_KEY` (secret), `AI_MODEL`, `DEMO_MODE`, `AUTO_FALLBACK_TO_MOCK`, `BATCH_SIZE_LIMIT`
4. Set **Health Check Path** to `/health/live` (also in [`render.yaml`](render.yaml))
5. Optional: deploy via [`render.yaml`](render.yaml) Blueprint

### Cloud caveats

- Free tier **sleeps after ~15 min idle** — cold start ~30–60s on first request; wake with `/health/live` before demo
- [`app/state.py`](app/state.py) in-memory export lost on cold start/redeploy — run batch again before `GET /tickets/export`
- [`app/config.py`](app/config.py) loads `.env` only if present; Render uses OS env vars
- Public Swagger — anyone with the URL can call endpoints and consume Gemini quota (acceptable for demo)
- CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs `pytest -q` on push/PR to `main`

Local dev unchanged: `.\run.ps1` with `--reload`.

---

## Architecture

```
HTTP (Swagger / curl)
  → app/main.py              routes, validation hints, custom OpenAPI
  → app/model_selection.py   GeminiModel enum, resolve_model()
  → app/services/            classify_ticket (with fallback), analyze_batch
  → app/providers/factory.py → GeminiProvider | MockProvider
  → google-genai API         OR keyword heuristics
  → Pydantic response models
  → app/state.py             in-memory last batch + CSV export
```

### Key files

| File | Role |
|------|------|
| `app/main.py` | Routes, exception handlers, custom OpenAPI; `GET /` → `/docs`; `GET /health/live` for Render |
| `app/models.py` | Pydantic schemas; `TICKET_EXAMPLE`; `created_at` hidden from OpenAPI via `SkipJsonSchema` |
| `app/model_selection.py` | `GeminiModel` enum, `SUPPORTED_GEMINI_MODELS`, `resolve_model()` |
| `app/config.py` | Settings from env vars + optional `.env` (`get_settings()` is `@lru_cache`) |
| `app/providers/factory.py` | Provider selection; accepts optional `model` override |
| `app/providers/gemini_provider.py` | Gemini JSON-mode calls; `ping()` returns `(reachable, detail)` |
| `app/providers/errors.py` | `ProviderUnavailableError` for 401/403/429 |
| `app/providers/mock_provider.py` | Keyword-based demo classifications |
| `app/services/classifier.py` | Classify with auto-fallback to mock on provider errors |
| `app/services/batch_analyzer.py` | Batch loop + trend analysis + fallback trends |
| `app/state.py` | CSV parse/upload, last batch storage, export |
| `data/sample_tickets.csv` | 20 demo tickets for batch upload demo |
| `.env` | Secrets — **never commit** (in `.gitignore`) |
| `.env.example` | Committed template |
| `run.ps1` | Local dev: uvicorn from `.venv` with `--reload` |
| `Dockerfile` | Production container; uvicorn on `$PORT` |
| `.dockerignore` | Excludes `.venv`, `.env`, tests from image |
| `render.yaml` | Render Blueprint (free web service, `healthCheckPath: /health/live`) |
| `.github/workflows/ci.yml` | pytest on push/PR |
| `tests/test_api.py` | 13 API tests (demo mode; no live Gemini) |

### Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/` | Redirects to `/docs` (hidden from OpenAPI) |
| GET | `/models` | Supported Gemini models + default from env (hardcoded list) |
| GET | `/health/live` | Fast liveness probe for Render; no Gemini call (hidden from OpenAPI) |
| GET | `/health` | Status, provider, Gemini ping; optional `?model=` |
| POST | `/tickets/classify` | Single ticket; optional `?model=` |
| POST | `/tickets/analyze-batch` | JSON `{ "tickets": [...] }`; optional `?model=` |
| POST | `/tickets/analyze-batch/upload` | CSV upload; optional `?model=` |
| GET | `/tickets/export` | CSV of last batch (404 if none yet) |

Responses include `model` (requested/effective) and `demo_mode` (true when mock was used).

---

## Environment variables (`.env` / Render dashboard)

```env
AI_PROVIDER=gemini
AI_API_KEY=your_gemini_api_key_here    # from Google AI Studio (AIzaSy...)
AI_MODEL=gemini-2.0-flash-lite       # default model; see GET /models
DEMO_MODE=false                      # true = always mock, no Gemini calls
AUTO_FALLBACK_TO_MOCK=true           # false = return HTTP 503 on Gemini quota/auth errors
BATCH_SIZE_LIMIT=10
```

Copy from `.env.example`. **Never commit `.env`.** Rotate any API key that was exposed in chat or logs.

---

## Model selection

Free-tier Gemini quotas are **per model**. If one model returns 429, try another.

| How | Example |
|-----|---------|
| Default | `AI_MODEL=gemini-2.5-flash-lite` in `.env` or Render env |
| Per request | `POST /tickets/classify?model=gemini-2.5-flash-lite` |
| List options | `GET /models` |
| Test connectivity | `GET /health?model=gemini-2.0-flash-lite` |

Supported IDs (also in `GeminiModel` enum):  
`gemini-2.0-flash-lite`, `gemini-2.0-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`

Swagger shows `model` as a **dropdown** (enum), not free text.

---

## Troubleshooting

### Swagger shows `TypeError: NetworkError when attempting to fetch resource`

**Usually a browser-side block, not a server bug.** Confirmed on Render deploy: `curl` and direct address-bar requests to `/health` return 200; failed Swagger requests often never appear in server logs.

**Most common cause:** ad blocker / privacy extension (uBlock Origin, Privacy Badger, etc.) silently cancels Swagger UI's background `fetch()`. Console may be empty.

**Fix:** disable the blocker for `arrow-2mz5.onrender.com`, or use a browser/profile without extensions. For interviews, test Swagger **Execute** once before the demo.

**Not the cause (ruled out during debug):** server crash, CORS misconfiguration on same-origin requests, OpenAPI `anyOf` schema (when present, server still responds to curl).

### `/health` shows `degraded` with quota message

**Expected when Gemini free tier is exhausted.** `/health` pings Gemini and surfaces the specific error (e.g. `429 quota exceeded`).

**Options:** switch model (see above), set `DEMO_MODE=true`, wait for quota reset, or use a new AI Studio key.

Classify/batch may still return **200** via mock fallback when `AUTO_FALLBACK_TO_MOCK=true` (default).

### Render cold start

First request after ~15 min idle may take 30–60s. Open `/health/live` in a tab and wait for `{"status":"ok"}` before using Swagger.

### `ModuleNotFoundError: pydantic_settings`

Use `.\run.ps1` or `.venv\Scripts\uvicorn` — not global Python.

### Port 8000 already in use

Stop stale uvicorn processes or use `--port 8001`.

### Swagger looked like it returned 422 while server returned 200

**Fixed.** FastAPI auto-documented 422 “Validation Error” in the Responses section (documentation only, not a runtime failure). Custom OpenAPI now removes 422 from docs. `created_at` is hidden from the request schema; `model` uses an enum dropdown.

### Request validation 422 (real errors)

Still possible for invalid JSON bodies. Validation handler adds hints for common Swagger mistakes (`created_at: "string"`, `demo_mode` in body). `created_at: "string"` is also coerced to `null` server-side.

---

## Testing

```powershell
.\.venv\Scripts\pytest -q
```

13 tests in `tests/test_api.py`. Tests set `DEMO_MODE=true` and empty `AI_API_KEY` before importing the app — they never call live Gemini.

Covers: health live, health, model list, classify, batch, CSV upload, export, mock fallback, OpenAPI 422 hidden, model override.

---

## Git & what is committed

Core app: `app/`, `tests/`, `data/`, `README.md`, `requirements.txt` (pinned), `.env.example`, `.gitignore`, `pytest.ini`, `run.ps1`.

Cloud/CI: `Dockerfile`, `.dockerignore`, `render.yaml`, `.github/workflows/ci.yml`.

**Not committed (intentional):** `.env`, `.venv/`, `AGENT_HANDOFF.md`, `*.code-workspace`, debug logs.

To publish updates: `git push origin main` → Render auto-rebuilds.

---

## Interview context

- **Preferred demo URL:** https://arrow-2mz5.onrender.com/docs (no local server needed)
- Local fallback: http://localhost:8000/docs via `.\run.ps1`
- Batch demo file: `data/sample_tickets.csv`
- Export path: `GET /tickets/export` → Power BI
- Prefer `DEMO_MODE=false` for live AI portion if quota allows; fall back to mock gracefully
- Wake Render instance with `/health/live` before live demo if service was idle
- Disable ad blocker for Render domain before Swagger demo
- ~5 min demo script in `README.md`

---

## Suggested next work (optional)

1. Add API key auth or rate limiting for production hardening
2. Persist batch results (DB) instead of in-memory `app/state.py`
3. Webhook ingest endpoint for Salesforce / Zendesk-style integrations
4. Custom domain on Render for cleaner interview URL

---

## Agent guidelines

1. **Use `.venv`** for all Python commands and uvicorn.
2. **Do not commit** `.env`, keys, or debug log files.
3. **Restart server** after `.env` changes (`get_settings` is cached).
4. **Minimize scope** — match existing patterns in `app/providers/` and `app/services/`.
5. **Run `pytest -q`** before finishing changes.
6. **User docs** live in `README.md`; keep this file accurate for agents, not end users.
7. **Render health checks** must use `/health/live`, not `/health` (avoids Gemini ping on every probe).

---

## Dependencies

See `requirements.txt` — pinned versions for reproducible local and Render builds.

Uses `google-genai` (not deprecated `google-generativeai`).
