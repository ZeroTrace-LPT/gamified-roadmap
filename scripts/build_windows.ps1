$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$version = (Get-Content "VERSION" -Raw).Trim()
$appName = "CybersecurityRoadmap-v$version"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

# Build with the interpreter and Windows DLL directories only. Unrelated tools on
# PATH can provide conflicting libraries (for example, another ICU build) that
# PyInstaller would otherwise collect beside the Qt runtime.
$originalPath = $env:PATH
try {
    $pythonBase = (& $python -c "import sys; print(sys.base_prefix)").Trim()
    $safePathEntries = @(
        (Split-Path -Parent $python),
        $pythonBase,
        (Join-Path $pythonBase "DLLs"),
        (Join-Path $env:SystemRoot "System32"),
        $env:SystemRoot
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
    $env:PATH = $safePathEntries -join [System.IO.Path]::PathSeparator

    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name $appName `
        --exclude-module numpy `
        --exclude-module PIL `
        --exclude-module lxml `
        run_app.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    $env:PATH = $originalPath
}

Write-Host "Build complete: $projectRoot\dist\$appName\$appName.exe"
