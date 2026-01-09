# Build and Test Script for Nestify (PowerShell)
# Builds the Python core (if pyproject.toml exists) and runs tests (pytest)

param(
    [switch]$NoBuild,
    [switch]$NoTest
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Resolve repo root
$Root = Split-Path -Path $PSScriptRoot -Parent
Push-Location $Root

try {
    Write-Info "Workspace: $Root"

    $pyproject = Join-Path $Root 'pyproject.toml'
    $hasPyproject = Test-Path $pyproject

    if (-not $NoBuild) {
        if ($hasPyproject) {
            Write-Info 'Building Python package via `python -m build`'
            $pythonCmds = @('py -m', 'python -m')
            $built = $false
            foreach ($pc in $pythonCmds) {
                try {
                    & powershell -NoProfile -Command "$pc pip install --upgrade build" | Out-Null
                    & powershell -NoProfile -Command "$pc build"
                    $built = $true
                    break
                } catch {
                    Write-Warn "Build attempt failed for command: $pc"
                }
            }
            if (-not $built) { Write-Err 'Failed to build package. Ensure Python is installed and `build` is available.' }
        } else {
            Write-Warn 'pyproject.toml not found. Skipping build.'
        }
    } else {
        Write-Info 'Skipping build per flag.'
    }

    if (-not $NoTest) {
        Write-Info 'Running tests (pytest)'
        $pytestFound = Get-Command pytest -ErrorAction SilentlyContinue
        if ($pytestFound) {
            pytest
        } else {
            Write-Warn 'pytest not found in PATH. Attempting to run via python.'
            $ran = $false
            foreach ($pc in @('py -m', 'python -m')) {
                try {
                    & powershell -NoProfile -Command "$pc pip install --upgrade pytest" | Out-Null
                    & powershell -NoProfile -Command "$pc pytest"
                    $ran = $true
                    break
                } catch {
                    Write-Warn "pytest run failed for command: $pc"
                }
            }
            if (-not $ran) { Write-Err 'Failed to run tests. Please ensure Python/pytest are installed.' }
        }
    } else {
        Write-Info 'Skipping tests per flag.'
    }
}
finally {
    Pop-Location
}
