$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name CybersecurityRoadmap `
    --exclude-module numpy `
    --exclude-module PIL `
    --exclude-module lxml `
    run_app.py

Write-Host "Build complete: $projectRoot\dist\CybersecurityRoadmap\CybersecurityRoadmap.exe"
