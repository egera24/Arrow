# Start the API using the project virtual environment
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\uvicorn.exe")) {
    Write-Host "Virtual environment not found. Run:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting Support Ticket Intelligence API on http://localhost:8000/docs" -ForegroundColor Green
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
