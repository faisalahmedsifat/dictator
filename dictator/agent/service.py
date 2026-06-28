"""AgentService: Orchestrates command execution via pluggable AI backends (Strategy pattern)."""

from __future__ import annotations

import json
import logging
import sys

from dictator.agent.backends import AIBackend, NullBackend, create_backend
from dictator.agent.commands import CommandRegistry
from dictator.agent.sandbox import CommandSandbox
from dictator.core.resilience import CircuitBreaker

logger = logging.getLogger(__name__)

TOOL_ROUTING_PROMPT = """\
You are a voice assistant command router on {platform}. Given the user's spoken command, \
determine which tool to call and with what arguments.

Available tools:
{tools_json}

Respond with ONLY a JSON object in this format (no markdown, no extra text):
{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}

If the command doesn't match any tool, respond with:
{{"name": "none", "arguments": {{}}}}

User command: {user_text}"""


class AgentService:
    """Orchestrates AI-powered command processing using pluggable backends.

    The backend (Strategy) is injected at construction time and can be any
    implementation of AIBackend — Claude, Copilot, Gemini, Ollama, or custom.
    Switch backends by changing a single config value.
    """

    def __init__(self, registry: CommandRegistry, backend: AIBackend | None = None):
        self._registry = registry
        self._sandbox = CommandSandbox(registry)
        self._backend: AIBackend = backend or NullBackend()
        self._circuit = CircuitBreaker(name="agent_cli", failure_threshold=3, reset_timeout=60.0)
        self._platform = "Windows" if sys.platform == "win32" else "Linux"

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def is_available(self) -> bool:
        """Check if the agent is operational."""
        return self._circuit.is_available and self._backend.is_available

    def swap_backend(self, new_backend: AIBackend) -> None:
        """Hot-swap the AI backend at runtime (e.g. from settings UI)."""
        logger.info(f"Swapping agent backend: {self._backend.name} -> {new_backend.name}")
        self._backend = new_backend
        self._circuit.reset()

    def process_command(self, user_text: str) -> str:
        """Process a voice command through the configured AI backend."""
        if not self._backend.is_available:
            return f"Agent unavailable ({self._backend.name} not found)"

        if not self._circuit.is_available:
            return "Agent temporarily unavailable (circuit breaker open)"

        result = self._circuit.call(
            self._route_command,
            user_text,
            fallback=lambda: "Agent temporarily unavailable",
        )
        return result or "No response from agent."

    def _route_command(self, user_text: str) -> str:
        """Use the backend to interpret the command and route to a tool."""
        tools_json = json.dumps(self._registry.get_tool_schemas(), indent=2)
        prompt = TOOL_ROUTING_PROMPT.format(
            platform=self._platform,
            tools_json=tools_json,
            user_text=user_text[:500],
        )

        response = self._backend.query(prompt)
        if not response:
            return "Agent could not process the command."

        return self._parse_and_execute(response)

    def _parse_and_execute(self, response: str) -> str:
        """Parse the backend's JSON response and execute the matched command."""
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            tool_call = json.loads(response)
            name = tool_call.get("name", "none")
            arguments = tool_call.get("arguments", {})

            if name == "none":
                return "I don't have a tool for that command."

            logger.info(f"Agent tool call: {name}({arguments})")
            return self._sandbox.execute(name, arguments)

        except json.JSONDecodeError:
            logger.warning(f"Could not parse agent response as JSON: {response[:200]}")
            return response[:500] if response else "Agent returned an unparseable response."
        except (KeyError, TypeError) as e:
            logger.error(f"Malformed tool call response: {e}")
            return "Agent returned a malformed response."
