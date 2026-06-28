"""Command pattern: Abstract command interface and registry for agent tools."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class Command(ABC):
    """Abstract base for all agent tool commands.

    Each command declares its name, description, parameter schema, and validation logic.
    Commands are self-contained and registered in the CommandRegistry.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this command."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this command does."""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing accepted parameters."""

    @abstractmethod
    def execute(self, args: dict[str, Any]) -> str:
        """Execute the command with validated arguments. Returns a result string."""

    def validate(self, args: dict[str, Any]) -> str | None:
        """Validate inputs before execution. Returns error message or None if valid.

        Default implementation checks required fields from the schema.
        Override for custom validation logic.
        """
        required = self.parameters.get("required", [])
        properties = self.parameters.get("properties", {})

        for field in required:
            if field not in args:
                return f"Missing required field: {field}"

        for field, value in args.items():
            if field in properties:
                schema = properties[field]
                error = self._validate_field(field, value, schema)
                if error:
                    return error

        return None

    def get_tool_schema(self) -> dict[str, Any]:
        """Generate OpenAI-compatible tool schema for LLM consumption."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def _validate_field(self, field: str, value: Any, schema: dict) -> str | None:
        expected_type = schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            return f"Field '{field}' must be a string"
        if expected_type == "integer" and not isinstance(value, int):
            return f"Field '{field}' must be an integer"
        if "enum" in schema and value not in schema["enum"]:
            return f"Field '{field}' must be one of: {schema['enum']}"
        return None


class CommandRegistry:
    """Registry of available commands. Generates tool schemas and dispatches execution."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register a command. Overwrites existing command with same name."""
        self._commands[command.name] = command
        logger.debug(f"Registered command: {command.name}")

    def unregister(self, name: str) -> None:
        self._commands.pop(name, None)

    def get(self, name: str) -> Command | None:
        """Look up a command by name."""
        return self._commands.get(name)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Generate the full tool list for LLM tool-calling."""
        return [cmd.get_tool_schema() for cmd in self._commands.values()]

    @property
    def available_commands(self) -> list[str]:
        return list(self._commands.keys())
