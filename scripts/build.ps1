# Build and Test Script for Nestify (PowerShell)
# Builds the Python core (if pyproject.toml exists) and runs tests (pytest)

param(
    [switch]$NoBuild,
    [switch]$NoTest,
    [switch]$BuildExtension,
    [switch]$PackageExtension,
    [switch]$InstallExtension
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

    # VS Code extension build/package/install (build by default if present)
    $extDir = Join-Path $Root 'vscode-extension'
    $pkgJson = Join-Path $extDir 'package.json'
    if (Test-Path $pkgJson) {
        Push-Location $extDir
        try {
            Write-Info 'Building VS Code extension (npm install + compile)'
            npm install
            npm run compile

            $vsixPath = $null
            if ($PackageExtension) {
                Write-Info 'Packaging VS Code extension via vsce'
                try {
                    $pkgOutput = npx vsce package 2>&1
                    Write-Info ($pkgOutput | Out-String)
                    # Try to find generated VSIX in folder
                    $vsix = Get-ChildItem -Filter '*.vsix' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
                    if ($vsix) { $vsixPath = $vsix.FullName; Write-Info "VSIX generated: $vsixPath" }
                    else { Write-Warn 'VSIX not found after packaging.' }
                } catch {
                    Write-Err 'Failed to package extension. Ensure vsce is available (npm i -g @vscode/vsce or use npx).'
                }
            }

            if ($InstallExtension) {
                if (-not $vsixPath) {
                    # Locate latest VSIX if not packaged in this run
                    $vsix = Get-ChildItem -Filter '*.vsix' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
                    if ($vsix) { $vsixPath = $vsix.FullName }
                }
                if ($vsixPath) {
                    Write-Info "Installing VSIX into VS Code: $vsixPath"
                    code --install-extension "$vsixPath"
                } else {
                    Write-Warn 'No VSIX found to install. Run with -PackageExtension or place a VSIX in vscode-extension.'
                }
            }
        }
        finally {
            Pop-Location
        }
    } else {
        Write-Warn 'vscode-extension/package.json not found. Skipping extension steps.'
    }
}
finally {
    Pop-Location
}
