"""Builder + Facade patterns: AppBuilder constructs DictatorApp which orchestrates all subsystems."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from dictator.agent.commands import CommandRegistry
from dictator.agent.service import AgentService
from dictator.agent.tools.app_launcher import AppLaunchCommand
from dictator.agent.tools.browser import OpenBrowserCommand
from dictator.agent.tools.keys import SimulateKeysCommand
from dictator.agent.tools.reactor import ReactorCommand
from dictator.agent.tools.volume import SystemVolumeCommand
from dictator.audio.sounds import SoundPlayer
from dictator.audio.stream import AudioStream
from dictator.core.config import AppConfig
from dictator.core.events import Event, EventBus, EventType
from dictator.core.lifecycle import LifecycleManager
from dictator.core.models import ModelManager
from dictator.core.resilience import HealthMonitor
from dictator.core.states import State, StateID, StateMachine
from dictator.core.transcription import TranscriptionResult, WhisperTranscriptionPipeline
from dictator.platform.factory import PlatformFactory, get_platform_factory
from dictator.platform.interfaces import Notifier, TextInjector, WindowContext
from dictator.platform.safety import SafeTextInjector
from dictator.ui.hotkeys import HotkeyManager
from dictator.ui.overlay import OverlayUI
from dictator.ui.presence import PresenceManager
from dictator.ui.tray import SystemTray
from dictator.utils.text import clean_text

logger = logging.getLogger(__name__)

ROUTING_DURATION = 4.0
DICTATION_KEYWORDS = ("dictat", "typing", "typ", "write this")
AGENT_KEYWORDS = ("start agent", "co-pilot", "copilot", "lets talk", "let's talk")
EXIT_COMMANDS = ("stop", "exit", "quit", "go to sleep", "close agent")


# --- Concrete State implementations ---

class IdleState(State):
    state_id = StateID.IDLE
    max_duration = 0

    def __init__(self, app: DictatorApp):
        self._app = app

    def enter(self, machine: StateMachine) -> None:
        self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "idle"))

    def handle_audio(self, machine: StateMachine, chunk: Any) -> None:
        if self._app.presence.is_suppressed:
            return
        word = self._app.wake_listener.process_chunk(chunk)
        if word:
            logger.info(f"Wake word detected: {word}")
            self._app.event_bus.publish(Event(EventType.TEXT_UPDATED, "I'm listening..."))
            self._app.sounds.play("wake")
            machine.transition_to(StateID.ROUTING)

    def handle_transcription(self, machine: StateMachine, result: TranscriptionResult) -> None:
        pass

    def exit(self, machine: StateMachine) -> None:
        pass


class RoutingState(State):
    state_id = StateID.ROUTING
    max_duration = 10.0

    def __init__(self, app: DictatorApp):
        self._app = app
        self._captured = ""
        self._start_time = 0.0

    def enter(self, machine: StateMachine) -> None:
        self._captured = ""
        self._start_time = time.time()
        self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "listening"))
        self._app.pipeline.reset()

    def handle_audio(self, machine: StateMachine, chunk: Any) -> None:
        pass

    def handle_transcription(self, machine: StateMachine, result: TranscriptionResult) -> None:
        if result.text:
            self._app.event_bus.publish(Event(EventType.TEXT_UPDATED, result.text))
            self._captured = result.text

        if time.time() - self._start_time > ROUTING_DURATION or result.is_final:
            self._route(machine)

    def _route(self, machine: StateMachine) -> None:
        cmd = self._captured.lower().strip()
        logger.info(f"Routing captured: '{cmd}'")

        if any(k in cmd for k in DICTATION_KEYWORDS):
            self._app.notifier.notify("Dictator", "Starting Dictation")
            self._app.sounds.play("success")
            self._app.pipeline.reset()
            machine.transition_to(StateID.DICTATING)

        elif any(k in cmd for k in AGENT_KEYWORDS):
            self._app.notifier.notify("Dictator", "Agent Mode")
            self._app.sounds.play("success")
            self._app.pipeline.reset()
            machine.transition_to(StateID.AGENT_LOOP)

        elif cmd:
            self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "processing"))
            self._app.event_bus.publish(Event(EventType.LOG_MESSAGE, f"User: {cmd}"))
            self._app.sounds.play("success")
            response = self._app.agent.process_command(cmd)
            self._app.event_bus.publish(Event(EventType.AGENT_RESPONSE, response))
            machine.transition_to(StateID.IDLE)
        else:
            machine.transition_to(StateID.IDLE)

    def exit(self, machine: StateMachine) -> None:
        pass


class DictatingState(State):
    state_id = StateID.DICTATING
    max_duration = 0

    def __init__(self, app: DictatorApp):
        self._app = app
        self._committed = ""

    def enter(self, machine: StateMachine) -> None:
        self._committed = ""
        self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "listening"))
        self._app.event_bus.publish(Event(EventType.TEXT_UPDATED, "Dictating..."))
        self._app.injector.reset_tracking()

    def handle_audio(self, machine: StateMachine, chunk: Any) -> None:
        pass

    def handle_transcription(self, machine: StateMachine, result: TranscriptionResult) -> None:
        if result.text:
            self._app.event_bus.publish(Event(EventType.TEXT_UPDATED, result.text))

        if result.is_final:
            text = clean_text(result.text)
            if self._committed:
                self._app.injector.backspace(len(self._committed))
                self._committed = ""
            if text:
                self._app.injector.type_text(text + " ")
        else:
            text = clean_text(result.text)
            if self._app.config.whisper.partial_typing:
                if self._committed:
                    self._app.injector.backspace(len(self._committed))
                if text:
                    self._app.injector.type_text(text)
                self._committed = text

    def exit(self, machine: StateMachine) -> None:
        self._committed = ""
        self._app.pipeline.reset()


class AgentLoopState(State):
    state_id = StateID.AGENT_LOOP
    max_duration = 0

    def __init__(self, app: DictatorApp):
        self._app = app

    def enter(self, machine: StateMachine) -> None:
        self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "agent"))
        self._app.event_bus.publish(Event(EventType.TEXT_UPDATED, "Agent Listening..."))
        self._app.pipeline.reset()

    def handle_audio(self, machine: StateMachine, chunk: Any) -> None:
        pass

    def handle_transcription(self, machine: StateMachine, result: TranscriptionResult) -> None:
        if result.text:
            self._app.event_bus.publish(Event(EventType.TEXT_UPDATED, result.text))

        if not result.is_final or not result.text:
            return

        cmd = result.text.lower().strip()
        logger.info(f"Agent command: '{cmd}'")
        self._app.event_bus.publish(Event(EventType.LOG_MESSAGE, f"User: {cmd}"))

        if cmd in EXIT_COMMANDS:
            self._app.notifier.notify("Dictator", "Agent Sleeping")
            self._app.sounds.play("exit")
            machine.transition_to(StateID.IDLE)
            return

        self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "processing"))
        response = self._app.agent.process_command(cmd)
        self._app.event_bus.publish(Event(EventType.AGENT_RESPONSE, response))
        self._app.sounds.play("success")
        self._app.event_bus.publish(Event(EventType.STATUS_CHANGED, "agent"))
        self._app.pipeline.reset()

    def exit(self, machine: StateMachine) -> None:
        self._app.pipeline.reset()


# --- Application Facade ---

class DictatorApp:
    """Facade: provides a simple start/stop interface to the entire system."""

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        lifecycle: LifecycleManager,
        platform: PlatformFactory,
        model_manager: ModelManager,
    ):
        self.config = config
        self.event_bus = event_bus
        self.lifecycle = lifecycle

        # Platform services
        window_ctx = platform.create_window_context()
        raw_injector = platform.create_injector()
        self.injector = SafeTextInjector(raw_injector, window_ctx)
        self.notifier = platform.create_notifier()
        volume_ctrl = platform.create_volume_controller()
        app_launcher = platform.create_app_launcher()

        # Models
        self.model_manager = model_manager

        # Audio
        self.audio_stream = AudioStream(device=config.audio.device)
        self.sounds = SoundPlayer()

        # Transcription pipeline
        self.pipeline = WhisperTranscriptionPipeline(event_bus, model_manager)

        # Wake word listener
        self.wake_listener = self._create_wake_listener()

        # Agent
        registry = CommandRegistry()
        registry.register(OpenBrowserCommand())
        registry.register(SystemVolumeCommand(volume_ctrl))
        registry.register(AppLaunchCommand(app_launcher))
        registry.register(SimulateKeysCommand())
        registry.register(ReactorCommand(window_ctx))
        self.agent = AgentService(registry, model_manager)

        # UI
        self.overlay = OverlayUI(event_bus, auto_hide_seconds=config.overlay.auto_hide_seconds)
        self.presence = PresenceManager(config.presence, window_ctx)
        self.tray = SystemTray(
            event_bus,
            on_toggle_dictation=self._toggle_dictation,
            on_toggle_agent=self._toggle_agent,
            on_quit=self._quit,
        )

        # State machine
        states = {
            StateID.IDLE: IdleState(self),
            StateID.ROUTING: RoutingState(self),
            StateID.DICTATING: DictatingState(self),
            StateID.AGENT_LOOP: AgentLoopState(self),
        }
        self.state_machine = StateMachine(states, StateID.IDLE, event_bus)

        # Health monitor
        self.health = HealthMonitor()
        self.health.register_check("audio", lambda: self.audio_stream.is_active)
        self.health.register_check("ui", lambda: self.overlay.is_alive())

        # Register cleanups
        lifecycle.register_cleanup("audio_stream", self.audio_stream.stop)
        lifecycle.register_cleanup("overlay_ui", self.overlay.stop)
        lifecycle.register_cleanup("tray_icon", self.tray.stop)
        lifecycle.register_cleanup("presence", self.presence.stop)

    def start(self) -> None:
        """Start all subsystems and enter the main loop."""
        logger.info("Dictator starting...")

        self.lifecycle.start()
        self.overlay.start()
        self.tray.start()
        self.presence.start()

        # Hotkeys
        hotkey_mgr = HotkeyManager(self.config.keybindings, self.event_bus)
        hotkey_mgr.start({
            "toggle_dictation": self._toggle_dictation,
            "toggle_agent": self._toggle_agent,
            "toggle_overlay": self._toggle_overlay,
            "toggle_log": self._toggle_log,
            "hide_all": self._hide_all,
            "cancel_current": self._cancel,
        })
        self.lifecycle.register_cleanup("hotkeys", hotkey_mgr.stop)

        # Load whisper model
        self.model_manager.get_whisper(self.config.whisper.model_size)

        # Start audio
        try:
            self.audio_stream.start()
        except Exception as e:
            logger.error(f"Failed to start audio: {e}")
            self.event_bus.publish(Event(EventType.TEXT_UPDATED, "No microphone detected"))
            self.event_bus.publish(Event(EventType.STATUS_CHANGED, "error"))

        self.event_bus.publish(Event(EventType.TEXT_UPDATED, "Dictator Ready (F9: Dictate, F10: Agent)"))

        # Main loop
        self._run_loop()

    def _run_loop(self) -> None:
        """Main processing loop: feed audio to state machine and transcription pipeline."""
        for chunk in self.audio_stream.iter_chunks():
            if self.lifecycle.is_shutting_down():
                break

            # Tick for timeout enforcement
            self.state_machine.tick()

            # Feed audio to current state (for wake word in IDLE)
            self.state_machine.handle_audio(chunk)

            # Run transcription if in a transcribing state
            current = self.state_machine.current_id
            if current in (StateID.ROUTING, StateID.DICTATING, StateID.AGENT_LOOP):
                for result in self.pipeline.run(iter([chunk])):
                    self.state_machine.handle_transcription(result)

    def _toggle_dictation(self) -> None:
        current = self.state_machine.current_id
        if current == StateID.DICTATING:
            self.sounds.play("exit")
            self.state_machine.transition_to(StateID.IDLE)
        else:
            self.sounds.play("success")
            self.pipeline.reset()
            self.state_machine.transition_to(StateID.DICTATING)

    def _toggle_agent(self) -> None:
        current = self.state_machine.current_id
        if current == StateID.AGENT_LOOP:
            self.sounds.play("exit")
            self.state_machine.transition_to(StateID.IDLE)
        else:
            self.sounds.play("success")
            self.pipeline.reset()
            self.state_machine.transition_to(StateID.AGENT_LOOP)

    def _toggle_overlay(self) -> None:
        self.event_bus.publish(Event(EventType.OVERLAY_TOGGLE, "toggle_main"))

    def _toggle_log(self) -> None:
        self.event_bus.publish(Event(EventType.OVERLAY_TOGGLE, "toggle_log"))

    def _hide_all(self) -> None:
        self.event_bus.publish(Event(EventType.OVERLAY_TOGGLE, "hide_all"))

    def _cancel(self) -> None:
        self.sounds.play("exit")
        self.state_machine.transition_to(StateID.IDLE)

    def _quit(self) -> None:
        self.lifecycle.request_shutdown()

    def _create_wake_listener(self):
        try:
            from openwakeword.model import Model as OWWModel
            from dictator.utils.paths import get_models_dir

            model_path = get_models_dir() / "hey_jarvis_v0.1.onnx"
            if model_path.exists():
                return WakeWordAdapter(str(model_path))
        except ImportError:
            pass
        return NullWakeListener()


class WakeWordAdapter:
    """Adapter wrapping openwakeword for the app's interface."""

    DETECTION_THRESHOLD = 0.6

    def __init__(self, model_path: str):
        import numpy as np
        from openwakeword.model import Model
        self._model = Model(wakeword_model_paths=[model_path])

    def process_chunk(self, chunk) -> str | None:
        import numpy as np
        chunk = np.clip(chunk, -1.0, 1.0).flatten()
        data = (chunk * 32768).astype(np.int16)
        self._model.predict(data)

        for mdl_name in self._model.prediction_buffer:
            score = self._model.prediction_buffer[mdl_name][-1]
            if score > self.DETECTION_THRESHOLD:
                self._model.reset()
                return mdl_name
        return None


class NullWakeListener:
    """No-op wake listener when openwakeword is unavailable."""

    def process_chunk(self, chunk) -> str | None:
        return None


# --- Builder ---

class AppBuilder:
    """Fluent builder for constructing DictatorApp with validation."""

    def __init__(self):
        self._config: AppConfig | None = None
        self._platform: PlatformFactory | None = None
        self._device: str | None = None
        self._model_size: str | None = None
        self._partial_typing: bool | None = None

    def with_config(self, config: AppConfig) -> AppBuilder:
        self._config = config
        return self

    def with_platform(self, platform: PlatformFactory) -> AppBuilder:
        self._platform = platform
        return self

    def with_device(self, device: str | None) -> AppBuilder:
        self._device = device
        return self

    def with_model(self, model_size: str) -> AppBuilder:
        self._model_size = model_size
        return self

    def with_partial_typing(self, enabled: bool) -> AppBuilder:
        self._partial_typing = enabled
        return self

    def build(self) -> DictatorApp:
        """Construct and validate the DictatorApp."""
        config = self._config or AppConfig.load()

        # Apply CLI overrides
        if self._device is not None:
            config.audio.device = self._device
        if self._model_size is not None:
            config.whisper.model_size = self._model_size
        if self._partial_typing is not None:
            config.whisper.partial_typing = self._partial_typing

        # Validate
        issues = config.validate()
        if issues:
            logger.warning(f"Config validation issues: {issues}")

        platform = self._platform or get_platform_factory()
        event_bus = EventBus()
        lifecycle = LifecycleManager()
        model_manager = ModelManager()

        return DictatorApp(
            config=config,
            event_bus=event_bus,
            lifecycle=lifecycle,
            platform=platform,
            model_manager=model_manager,
        )
