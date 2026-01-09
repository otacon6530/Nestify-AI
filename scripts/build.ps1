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

    # VS Code extension build/package/install (auto-detect and run by default)
    $extCandidates = @(
        (Join-Path $Root 'vscode-extension'),
        (Join-Path (Join-Path $Root 'VSCodeExtension') 'codex-chat')
    )
    $extDir = $null
    $pkgJson = $null
    foreach ($d in $extCandidates) {
        $pj = Join-Path $d 'package.json'
        if (Test-Path $pj) { $extDir = $d; $pkgJson = $pj; break }
    }
    if ($pkgJson) {
        Push-Location $extDir
        try {
            Write-Info "Building VS Code extension in $extDir (npm install + compile/build)"
            npm install
            # Run compile if present; else try build
            try { npm run compile } catch { try { npm run build } catch { Write-Warn 'No compile/build script present, continuing.' } }

            Write-Info 'Packaging VS Code extension (prefer local vsce)'
            $vsixPath = $null
            try {
                if (Test-Path (Join-Path $extDir 'node_modules/.bin/vsce.cmd')) {
                    Write-Info 'Using local vsce via npm run package'
                    $pkgOutput = npm run package 2>&1
                } else {
                    $vsceCmd = Get-Command vsce -ErrorAction SilentlyContinue
                    if ($vsceCmd) {
                        Write-Info 'Using globally installed vsce'
                        $pkgOutput = vsce package 2>&1
                    } else {
                        Write-Info 'Using npx to run vsce'
                        $pkgOutput = npx vsce package 2>&1
                    }
                }
                Write-Info ($pkgOutput | Out-String)
            } catch {
                Write-Warn 'Packaging reported an error; will still look for VSIX.'
            }

            # Try to find generated VSIX in folder
            $vsix = Get-ChildItem -Filter '*.vsix' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($vsix) { $vsixPath = $vsix.FullName; Write-Info "VSIX located: $vsixPath" }
            else { Write-Err 'VSIX not found after packaging.' }

            if ($vsixPath) {
                Write-Info "Installing VSIX into VS Code: $vsixPath"
                code --install-extension "$vsixPath"
            }
        }
        finally {
            Pop-Location
        }
    } else {
        Write-Warn 'No VS Code extension package.json found. Skipping extension steps.'
    }
}
finally {
    Pop-Location
}
