param(
    [string]$EnvFile = ".env",
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    Copy-Item ".env.local.example" $EnvFile
    Write-Host "Created $EnvFile from .env.local.example. Add API keys before running live fact checks."
}

$env:EVIDENCECHAIN_ENV_FILE = $EnvFile
$env:EVIDENCECHAIN_HTTP_PORT = "$Port"

docker compose up --build
