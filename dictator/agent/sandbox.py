"""Command execution sandbox: timeout enforcement, input validation, error isolation."""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any

from dictator.agent.commands import Command, CommandRegistry

logger = logging.getLogger(__name__)


class CommandSandbox:
    """Wraps command execution with safety guarantees.

    - Validates inputs against command schema before execution
    - Enforces timeout on every command
    - Isolates exceptions so a failing command never crashes the agent
    """

    def __init__(self, registry: CommandRegistry, default_timeout: float = 10.0):
        self._registry = registry
        self._default_timeout = default_timeout

    def execute(self, command_name: str, args: dict[str, Any]) -> str:
        """Execute a command by name with full sandboxing."""
        command = self._registry.get(command_name)
        if not command:
            return f"Unknown command: {command_name}"

        # Step 1: Validate inputs
        validation_error = command.validate(args)
        if validation_error:
            logger.warning(f"Command '{command_name}' validation failed: {validation_error}")
            return f"Invalid input: {validation_error}"

        # Step 2: Execute with timeout
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(command.execute, args)
                result = future.result(timeout=self._default_timeout)
                return result
        except concurrent.futures.TimeoutError:
            logger.warning(f"Command '{command_name}' timed out after {self._default_timeout}s")
            return f"Command timed out after {self._default_timeout}s"
        except Exception as e:
            logger.error(f"Command '{command_name}' failed: {e}")
            return f"Command failed: {e}"
