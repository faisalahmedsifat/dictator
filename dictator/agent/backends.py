"""Strategy pattern: Pluggable AI backends for the agent service.

Each backend implements the same interface (AIBackend ABC) so they can be
swapped transparently via configuration. Add new backends by subclassing
AIBackend and registering in BACKEND_REGISTRY.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AIBackend(ABC):
    """Strategy interface for AI agent backends.

    All backends must implement `query()` which takes a text prompt and
    returns the AI's text response, and `is_available` which reports
    whether the backend can currently serve requests.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend is ready to handle queries."""

    @abstractmethod
    def query(self, prompt: str) -> str | None:
        """Send a prompt and return the response text, or None on failure."""


class CLIProcessBackend(AIBackend):
    """Base strategy for backends invoked as a subprocess CLI command.

    Subclasses override `_build_command()` to produce the correct argv
    for their specific CLI tool.
    """

    def __init__(self, executable: str, timeout: float = 30.0):
        self._executable = executable
        self._timeout = timeout
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which(self._executable) is not None
        return self._available

    def _build_command(self, prompt: str) -> list[str]:
        """Build the subprocess argv. Override in subclasses for tool-specific flags."""
        return [self._executable, prompt]

    def query(self, prompt: str) -> str | None:
        if not self.is_available:
            return None

        cmd = self._build_command(prompt)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            if result.stderr:
                logger.warning(f"{self.name} stderr: {result.stderr[:200]}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"{self.name} timed out after {self._timeout}s")
            return None
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return None


class ClaudeBackend(CLIProcessBackend):
    """Strategy for Anthropic's Claude Code CLI (`claude --print`)."""

    def __init__(self, timeout: float = 30.0):
        super().__init__(executable="claude", timeout=timeout)

    @property
    def name(self) -> str:
        return "Claude CLI"

    def _build_command(self, prompt: str) -> list[str]:
        return [self._executable, "--print", prompt]


class CopilotBackend(CLIProcessBackend):
    """Strategy for GitHub Copilot CLI (`gh copilot suggest`)."""

    def __init__(self, timeout: float = 30.0):
        super().__init__(executable="gh", timeout=timeout)

    @property
    def name(self) -> str:
        return "GitHub Copilot CLI"

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which("gh") is not None
        return self._available

    def _build_command(self, prompt: str) -> list[str]:
        return ["gh", "copilot", "suggest", "-t", "shell", prompt]


class GeminiBackend(CLIProcessBackend):
    """Strategy for Google's Gemini CLI (`gemini`)."""

    def __init__(self, timeout: float = 30.0):
        super().__init__(executable="gemini", timeout=timeout)

    @property
    def name(self) -> str:
        return "Gemini CLI"

    def _build_command(self, prompt: str) -> list[str]:
        return [self._executable, "-p", prompt]


class OllamaBackend(CLIProcessBackend):
    """Strategy for local Ollama models (`ollama run <model>`)."""

    def __init__(self, model: str = "llama3.2", timeout: float = 60.0):
        super().__init__(executable="ollama", timeout=timeout)
        self._model = model

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    def _build_command(self, prompt: str) -> list[str]:
        return [self._executable, "run", self._model, prompt]


class CustomBackend(CLIProcessBackend):
    """Strategy for any arbitrary CLI tool specified by the user.

    Uses the convention: `<executable> <prompt>` by default.
    Users can subclass or configure as needed.
    """

    def __init__(self, executable: str, args_template: list[str] | None = None, timeout: float = 30.0):
        super().__init__(executable=executable, timeout=timeout)
        self._args_template = args_template or []

    @property
    def name(self) -> str:
        return f"Custom ({self._executable})"

    def _build_command(self, prompt: str) -> list[str]:
        if self._args_template:
            return [self._executable] + [
                arg.replace("{prompt}", prompt) for arg in self._args_template
            ]
        return [self._executable, prompt]


class NullBackend(AIBackend):
    """Null Object pattern: no-op backend when agent is disabled."""

    @property
    def name(self) -> str:
        return "Disabled"

    @property
    def is_available(self) -> bool:
        return False

    def query(self, prompt: str) -> str | None:
        return None


# --- Factory Registry ---

BACKEND_REGISTRY: dict[str, type[AIBackend]] = {
    "claude": ClaudeBackend,
    "copilot": CopilotBackend,
    "gemini": GeminiBackend,
    "ollama": OllamaBackend,
    "none": NullBackend,
    "disabled": NullBackend,
}


def create_backend(backend_name: str, timeout: float = 30.0) -> AIBackend:
    """Factory function: create the appropriate backend from a config string.

    Supports registered names (claude, copilot, gemini, ollama, none)
    and falls back to CustomBackend for unrecognized executables.
    """
    name_lower = backend_name.lower().strip()

    if name_lower in BACKEND_REGISTRY:
        cls = BACKEND_REGISTRY[name_lower]
        if cls is NullBackend:
            return NullBackend()
        if cls is OllamaBackend:
            return OllamaBackend(timeout=timeout)
        return cls(timeout=timeout)

    logger.info(f"Using custom backend for executable: {backend_name}")
    return CustomBackend(executable=backend_name, timeout=timeout)
