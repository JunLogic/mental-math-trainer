$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Find Python 3.10+
$python = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $version = & $cmd -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
        if ($version -eq "True") {
            $python = $cmd
            break
        }
    } catch {}
}

if (-not $python) {
    Write-Host "Error: Python 3.10 or newer is required." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/"
    exit 1
}

# Create virtual environment if needed
if (!(Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    & $python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

# Install dependencies only when needed
$marker = ".venv\.deps_installed"
$needsInstall = !(Test-Path $marker) -or ((Get-Item "requirements.txt").LastWriteTime -gt (Get-Item $marker).LastWriteTime)
if ($needsInstall) {
    Write-Host "Installing dependencies..."
    pip install -q -r requirements.txt
    New-Item -Path $marker -ItemType File -Force | Out-Null
}

Write-Host ""
Write-Host "=============================="
Write-Host "  Mental Math Trainer"
Write-Host "=============================="
Write-Host ""

python -m app.cli @args
