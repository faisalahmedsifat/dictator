# Dictator Local Test Script
# Tests that the package installs correctly and core modules load on your machine.
# Usage: .\scripts\test_local.ps1

param(
    [switch]$SkipInstall,
    [switch]$FullBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Dictator - Local Test Suite" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$pass = 0
$fail = 0
$skip = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "  [$Name] " -NoNewline -ForegroundColor White
    try {
        $result = & $Action
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Exit code: $LASTEXITCODE" }
        Write-Host "PASS" -ForegroundColor Green
        $script:pass++
    } catch {
        Write-Host "FAIL - $($_.Exception.Message)" -ForegroundColor Red
        $script:fail++
    }
}

function Skip-Step {
    param([string]$Name, [string]$Reason)
    Write-Host "  [$Name] " -NoNewline -ForegroundColor White
    Write-Host "SKIP ($Reason)" -ForegroundColor Yellow
    $script:skip++
}

# ============================================================
# PHASE 1: Environment Setup
# ============================================================
Write-Host "[Phase 1] Environment Setup" -ForegroundColor Yellow
Write-Host ""

if (-not $SkipInstall) {
    $VenvDir = Join-Path $ProjectRoot ".venv"
    if (-not (Test-Path $VenvDir)) {
        Write-Host "  Creating virtual environment..." -ForegroundColor Gray
        python -m venv $VenvDir
    }

    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
    . $ActivateScript

    Write-Host "  Installing package..." -ForegroundColor Gray
    pip install -e ".[windows,dev]" --quiet 2>&1 | Out-Null

    # openwakeword separate due to dep conflicts
    pip install openwakeword --no-deps --quiet 2>&1 | Out-Null
}

Write-Host ""

# ============================================================
# PHASE 2: Import Tests (verify all modules load)
# ============================================================
Write-Host "[Phase 2] Module Import Tests" -ForegroundColor Yellow
Write-Host ""

Test-Step "Package root" { python -c "import dictator; assert dictator.__version__ == '2.0.0'" }
Test-Step "core.events" { python -c "from dictator.core.events import EventBus, EventType, Event" }
Test-Step "core.states" { python -c "from dictator.core.states import StateMachine, State, StateID" }
Test-Step "core.config" { python -c "from dictator.core.config import AppConfig; c = AppConfig(); assert c.validate() == []" }
Test-Step "core.resilience" { python -c "from dictator.core.resilience import CircuitBreaker, RetryPolicy, HealthMonitor" }
Test-Step "core.lifecycle" { python -c "from dictator.core.lifecycle import LifecycleManager" }
Test-Step "core.models" { python -c "from dictator.core.models import ModelManager; m = ModelManager()" }
Test-Step "platform.interfaces" { python -c "from dictator.platform.interfaces import TextInjector, VolumeController, Notifier" }
Test-Step "platform.factory" { python -c "from dictator.platform.factory import get_platform_factory; f = get_platform_factory(); print(f'  Factory: {type(f).__name__}')" }
Test-Step "platform.null" { python -c "from dictator.platform.null import NullTextInjector, NullVolumeController, NullNotifier" }
Test-Step "platform.safety" { python -c "from dictator.platform.safety import SafeTextInjector" }
Test-Step "platform.windows" { python -c "from dictator.platform.windows import WindowsFactory, WindowsWindowContext" }
Test-Step "agent.commands" { python -c "from dictator.agent.commands import Command, CommandRegistry" }
Test-Step "agent.sandbox" { python -c "from dictator.agent.sandbox import CommandSandbox" }
Test-Step "agent.tools" { python -c "from dictator.agent.tools.browser import OpenBrowserCommand; from dictator.agent.tools.keys import SimulateKeysCommand" }
Test-Step "audio.stream" { python -c "from dictator.audio.stream import AudioStream" }
Test-Step "audio.sounds" { python -c "from dictator.audio.sounds import SoundPlayer" }
Test-Step "ui.overlay" { python -c "from dictator.ui.overlay import OverlayUI" }
Test-Step "ui.tray" { python -c "from dictator.ui.tray import SystemTray" }
Test-Step "ui.hotkeys" { python -c "from dictator.ui.hotkeys import HotkeyManager" }
Test-Step "ui.presence" { python -c "from dictator.ui.presence import PresenceManager" }
Test-Step "utils.paths" { python -c "from dictator.utils.paths import get_app_data_dir; d = get_app_data_dir(); print(f'  AppData: {d}')" }
Test-Step "app (builder)" { python -c "from dictator.app import AppBuilder" }

Write-Host ""

# ============================================================
# PHASE 3: Functional Tests
# ============================================================
Write-Host "[Phase 3] Functional Tests" -ForegroundColor Yellow
Write-Host ""

Test-Step "EventBus pub/sub" {
    python -c @"
from dictator.core.events import EventBus, Event, EventType
bus = EventBus()
received = []
bus.subscribe(EventType.TEXT_UPDATED, lambda e: received.append(e.data))
bus.publish(Event(EventType.TEXT_UPDATED, 'hello'))
assert received == ['hello'], f'Got: {received}'
"@
}

Test-Step "CircuitBreaker open/close" {
    python -c @"
from dictator.core.resilience import CircuitBreaker, CircuitState
cb = CircuitBreaker('test', failure_threshold=2, reset_timeout=0.1)
assert cb.state == CircuitState.CLOSED
cb.record_failure(RuntimeError('x'))
cb.record_failure(RuntimeError('x'))
assert cb.state == CircuitState.OPEN
import time; time.sleep(0.2)
assert cb.state == CircuitState.HALF_OPEN
"@
}

Test-Step "Config save/load" {
    python -c @"
from dictator.core.config import AppConfig
c = AppConfig()
c.audio.device = 'TestMic'
c.save()
c2 = AppConfig.load()
assert c2.audio.device == 'TestMic', f'Got: {c2.audio.device}'
"@
}

Test-Step "Command validation" {
    python -c @"
from dictator.agent.tools.browser import OpenBrowserCommand
cmd = OpenBrowserCommand()
err = cmd.validate({'url': 'javascript:alert(1)'})
assert err is not None, 'Should reject javascript: URLs'
err2 = cmd.validate({'url': 'https://example.com'})
assert err2 is None, f'Should accept https: {err2}'
"@
}

Test-Step "SimulateKeys blocks dangerous" {
    python -c @"
from dictator.agent.tools.keys import SimulateKeysCommand
cmd = SimulateKeysCommand()
err = cmd.validate({'keys': 'alt+f4'})
assert err is not None, 'Should block alt+f4'
err2 = cmd.validate({'keys': 'ctrl+c'})
assert err2 is None, 'Should allow ctrl+c'
"@
}

Test-Step "NullObject contracts" {
    python -c @"
from dictator.platform.null import *
inj = NullTextInjector()
assert inj.type_text('test') == False
assert inj.backspace(5) == False
vol = NullVolumeController()
assert vol.get_volume() == 0.5
ctx = NullWindowContext()
assert ctx.get_active_window_title() == ''
assert ctx.is_fullscreen() == False
"@
}

Test-Step "WindowsWindowContext title" {
    python -c @"
from dictator.platform.windows import WindowsWindowContext
ctx = WindowsWindowContext()
title = ctx.get_active_window_title()
# Should return something (we're running in a terminal)
assert isinstance(title, str)
print(f'  Active window: {title[:50]}')
"@
}

Test-Step "Text sanitization" {
    python -c @"
from dictator.utils.text import sanitize_for_injection, cap_length, clean_text
assert sanitize_for_injection('hello\x00world') == 'helloworld'
assert cap_length('x' * 10000, 100) == 'x' * 100
assert clean_text('the the cat') == 'the cat'
"@
}

Test-Step "Audio device listing" {
    python -c @"
from dictator.audio.stream import AudioStream
devices = AudioStream.list_devices()
print(f'  Found {len(devices)} input devices')
for d in devices[:3]:
    print(f'    [{d[\"index\"]}] {d[\"name\"]}')
"@
}

Write-Host ""

# ============================================================
# PHASE 4: Build Test (optional)
# ============================================================
if ($FullBuild) {
    Write-Host "[Phase 4] PyInstaller Build Test" -ForegroundColor Yellow
    Write-Host ""

    Test-Step "PyInstaller bundle" {
        pyinstaller installer\dictator.spec --noconfirm --clean 2>&1 | Out-Null
        if (-not (Test-Path "dist\Dictator\Dictator.exe")) { throw "EXE not found" }
        $size = [math]::Round((Get-Item "dist\Dictator\Dictator.exe").Length / 1MB, 1)
        Write-Host "  ($size MB)" -NoNewline -ForegroundColor Gray
    }
} else {
    Skip-Step "PyInstaller build" "Use -FullBuild flag to test"
}

Write-Host ""

# ============================================================
# Summary
# ============================================================
Write-Host "==========================================" -ForegroundColor Cyan
$total = $pass + $fail + $skip
Write-Host "  Results: $pass passed, $fail failed, $skip skipped (of $total)" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if ($fail -gt 0) {
    Write-Host "Some tests failed. Check output above for details." -ForegroundColor Red
    exit 1
} else {
    Write-Host "All tests passed! Ready to build installer." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Run full build:  .\installer\build.ps1" -ForegroundColor Gray
    Write-Host "  2. Or just bundle:  .\scripts\test_local.ps1 -FullBuild" -ForegroundColor Gray
    Write-Host ""
}
