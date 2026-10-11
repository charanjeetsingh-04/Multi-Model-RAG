# One-shot local dev setup (Windows PowerShell).
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env — open it and set GEMINI_API_KEY."
}

python -m venv .venv
& ".venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

New-Item -ItemType Directory -Force -Path uploads, vector_store, logs | Out-Null

Push-Location frontend; npm install; Pop-Location
Write-Host "Done. Next: docker compose up -d postgres redis ; alembic upgrade head"
