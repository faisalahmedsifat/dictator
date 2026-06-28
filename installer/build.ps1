# Dictator Windows Installer Build Script
# Usage: .\installer\build.ps1
# Prerequisites: Python 3.11+, PyInstaller, Inno Setup (iscc in PATH)

param(
    [switch]$SkipVenv,
    [switch]$SkipPyInstaller,
    [switch]$SkipInnoSetup,
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Dictator Windows Installer Builder" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Ensure virtual environment
if (-not $SkipVenv) {
    Write-Host "[1/4] Setting up virtual environment..." -ForegroundColor Yellow

    $VenvDir = Join-Path $ProjectRoot ".venv"
    if (-not (Test-Path $VenvDir)) {
        & $PythonPath -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Failed to create venv" }
    }

    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
    . $ActivateScript

    Write-Host "  Installing dependencies..." -ForegroundColor Gray
    pip install -e ".[windows,dev]" --quiet
    if ($LASTEXITCODE -ne 0) { throw "Failed to install dependencies" }

    # openwakeword needs special handling
    pip install openwakeword --no-deps --quiet 2>$null

    Write-Host "  Done." -ForegroundColor Green
} else {
    Write-Host "[1/4] Skipping venv setup." -ForegroundColor Gray
}

# Step 2: Run PyInstaller
if (-not $SkipPyInstaller) {
    Write-Host "[2/4] Building with PyInstaller..." -ForegroundColor Yellow

    $SpecFile = Join-Path $ProjectRoot "installer\dictator.spec"
    $DistDir = Join-Path $ProjectRoot "dist"

    # Clean previous build
    if (Test-Path $DistDir) {
        Remove-Item -Recurse -Force $DistDir
    }

    Push-Location $ProjectRoot
    pyinstaller $SpecFile --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    Pop-Location

    Write-Host "  PyInstaller build complete." -ForegroundColor Green
} else {
    Write-Host "[2/4] Skipping PyInstaller." -ForegroundColor Gray
}

# Step 3: Verify build output
Write-Host "[3/4] Verifying build..." -ForegroundColor Yellow

$ExePath = Join-Path $ProjectRoot "dist\Dictator\Dictator.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build verification failed: $ExePath not found"
}

$ExeSize = (Get-Item $ExePath).Length / 1MB
Write-Host "  Dictator.exe: $([math]::Round($ExeSize, 1)) MB" -ForegroundColor Gray

$TotalSize = (Get-ChildItem -Recurse (Join-Path $ProjectRoot "dist\Dictator") | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "  Total bundle: $([math]::Round($TotalSize, 1)) MB" -ForegroundColor Gray
Write-Host "  Build verified." -ForegroundColor Green

# Step 4: Run Inno Setup
if (-not $SkipInnoSetup) {
    Write-Host "[4/4] Creating installer with Inno Setup..." -ForegroundColor Yellow

    # Ensure icon exists
    $IconPath = Join-Path $ProjectRoot "installer\icon.ico"
    if (-not (Test-Path $IconPath)) {
        Write-Host "  Generating icon.ico..." -ForegroundColor Gray
        $GenScript = Join-Path $ProjectRoot "scripts\generate_icon.py"
        python $GenScript
        if ($LASTEXITCODE -ne 0) { Write-Host "  Warning: could not generate icon" -ForegroundColor Red }
    }

    $IssFile = Join-Path $ProjectRoot "installer\dictator.iss"
    $IsccPath = Get-Command "iscc" -ErrorAction SilentlyContinue

    if (-not $IsccPath) {
        # Try common install locations
        $CommonPaths = @(
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe"
        )
        foreach ($path in $CommonPaths) {
            if (Test-Path $path) {
                $IsccPath = $path
                break
            }
        }
    }

    if (-not $IsccPath) {
        Write-Host "  WARNING: Inno Setup (iscc) not found in PATH." -ForegroundColor Red
        Write-Host "  Install from: https://jrsoftware.org/isdl.php" -ForegroundColor Red
        Write-Host "  Skipping installer creation." -ForegroundColor Red
    } else {
        $IsccExe = if ($IsccPath -is [System.Management.Automation.CommandInfo]) { $IsccPath.Source } else { $IsccPath }
        & $IsccExe $IssFile
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

        $InstallerPath = Join-Path $ProjectRoot "dist\DictatorSetup-2.0.0.exe"
        if (Test-Path $InstallerPath) {
            $InstallerSize = (Get-Item $InstallerPath).Length / 1MB
            Write-Host "  Installer: $([math]::Round($InstallerSize, 1)) MB" -ForegroundColor Gray
        }
        Write-Host "  Installer created." -ForegroundColor Green
    }
} else {
    Write-Host "[4/4] Skipping Inno Setup." -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Outputs:" -ForegroundColor White
Write-Host "  Bundle: dist\Dictator\" -ForegroundColor Gray
Write-Host "  Installer: dist\DictatorSetup-2.0.0.exe" -ForegroundColor Gray
