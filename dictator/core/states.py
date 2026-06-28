"""State pattern: Application state machine with guarded transitions and timeout safety."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from dictator.core.events import Event, EventBus, EventType

if TYPE_CHECKING:
    from dictator.core.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class StateID(Enum):
    IDLE = auto()
    ROUTING = auto()
    DICTATING = auto()
    AGENT_LOOP = auto()


# Valid transition map: from_state -> set of allowed to_states
ALLOWED_TRANSITIONS: dict[StateID, set[StateID]] = {
    StateID.IDLE: {StateID.ROUTING, StateID.DICTATING, StateID.AGENT_LOOP},
    StateID.ROUTING: {StateID.IDLE, StateID.DICTATING, StateID.AGENT_LOOP},
    StateID.DICTATING: {StateID.IDLE},
    StateID.AGENT_LOOP: {StateID.IDLE},
}


class State(ABC):
    """Abstract base for all application states."""

    state_id: StateID
    max_duration: float = 0  # 0 means no timeout

    @abstractmethod
    def enter(self, machine: StateMachine) -> None:
        """Called when transitioning into this state."""

    @abstractmethod
    def handle_audio(self, machine: StateMachine, chunk: Any) -> None:
        """Process an audio chunk in this state."""

    @abstractmethod
    def handle_transcription(self, machine: StateMachine, result: TranscriptionResult) -> None:
        """Process a transcription result in this state."""

    def exit(self, machine: StateMachine) -> None:
        """Called when transitioning out of this state. Override for cleanup."""

    def tick(self, machine: StateMachine) -> None:
        """Called periodically. Used for timeout enforcement."""
        if self.max_duration > 0:
            elapsed = time.time() - machine.state_entered_at
            if elapsed > self.max_duration:
                logger.warning(
                    f"State {self.state_id.name} timed out after {elapsed:.1f}s "
                    f"(max {self.max_duration}s), returning to IDLE"
                )
                machine.transition_to(StateID.IDLE)


class StateMachine:
    """Manages application state with guarded transitions and event emission."""

    def __init__(self, states: dict[StateID, State], initial: StateID, event_bus: EventBus):
        self._states = states
        self._event_bus = event_bus
        self._current_id = initial
        self.state_entered_at: float = time.time()

        state = self._states[initial]
        state.enter(self)
        self._emit_state_change(initial)

    @property
    def current_state(self) -> State:
        return self._states[self._current_id]

    @property
    def current_id(self) -> StateID:
        return self._current_id

    def transition_to(self, target: StateID) -> bool:
        """Attempt a state transition. Returns False if transition is invalid."""
        if target == self._current_id:
            return True

        allowed = ALLOWED_TRANSITIONS.get(self._current_id, set())
        if target not in allowed:
            logger.warning(
                f"Rejected invalid transition: {self._current_id.name} -> {target.name}. "
                f"Allowed: {[s.name for s in allowed]}"
            )
            return False

        old_state = self._states[self._current_id]
        new_state = self._states[target]

        try:
            old_state.exit(self)
        except Exception as e:
            logger.error(f"Error exiting state {self._current_id.name}: {e}")

        old_id = self._current_id
        self._current_id = target
        self.state_entered_at = time.time()

        try:
            new_state.enter(self)
        except Exception as e:
            logger.error(f"Error entering state {target.name}: {e}, falling back to IDLE")
            self._current_id = StateID.IDLE
            self.state_entered_at = time.time()
            self._states[StateID.IDLE].enter(self)

        logger.info(f"State transition: {old_id.name} -> {self._current_id.name}")
        self._emit_state_change(self._current_id)
        return True

    def handle_audio(self, chunk: Any) -> None:
        """Delegate audio handling to current state with error recovery."""
        try:
            self.current_state.handle_audio(self, chunk)
        except Exception as e:
            logger.error(f"Error in {self._current_id.name}.handle_audio: {e}")
            self.transition_to(StateID.IDLE)

    def handle_transcription(self, result: Any) -> None:
        """Delegate transcription result to current state with error recovery."""
        try:
            self.current_state.handle_transcription(self, result)
        except Exception as e:
            logger.error(f"Error in {self._current_id.name}.handle_transcription: {e}")
            self.transition_to(StateID.IDLE)

    def tick(self) -> None:
        """Periodic tick for timeout enforcement."""
        try:
            self.current_state.tick(self)
        except Exception as e:
            logger.error(f"Error in {self._current_id.name}.tick: {e}")

    def _emit_state_change(self, state_id: StateID) -> None:
        self._event_bus.publish(Event(
            type=EventType.STATE_CHANGED,
            data=state_id.name,
            source="state_machine",
        ))
