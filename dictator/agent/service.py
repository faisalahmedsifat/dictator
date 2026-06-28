"""AgentService: Orchestrates command execution via external CLI AI tools (e.g. claude)."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from typing import Any

from dictator.agent.commands import CommandRegistry
from dictator.agent.sandbox import CommandSandbox
from dictator.core.resilience import CircuitBreaker

logger = logging.getLogger(__name__)


class CLIBackend:
    """Abstraction for invoking an external AI CLI tool in headless/non-interactive mode."""

    def __init__(self, executable: str = "claude", timeout: float = 30.0):
        self._executable = executable
        self._timeout = timeout
        self._available: bool | None = None

    @property
    def is_installed(self) -> bool:
        if self._available is None:
            self._available = shutil.which(self._executable) is not None
        return self._available

    def query(self, prompt: str) -> str | None:
        """Send a prompt to the CLI tool and return its text response."""
        if not self.is_installed:
            return None

        try:
            result = subprocess.run(
                [self._executable, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            if result.stderr:
                logger.warning(f"CLI backend stderr: {result.stderr[:200]}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"CLI backend timed out after {self._timeout}s")
            return None
        except Exception as e:
            logger.error(f"CLI backend error: {e}")
            return None


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
    """Orchestrates AI-powered command processing using external CLI tools.

    Uses claude (or other CLI AI tools) in headless mode to interpret voice
    commands and route them to the appropriate tool handlers.
    """

    def __init__(self, registry: CommandRegistry, backend: CLIBackend | None = None):
        self._registry = registry
        self._sandbox = CommandSandbox(registry)
        self._backend = backend or CLIBackend()
        self._circuit = CircuitBreaker(name="agent_cli", failure_threshold=3, reset_timeout=60.0)
        self._platform = "Windows" if sys.platform == "win32" else "Linux"

    @property
    def is_available(self) -> bool:
        """Check if the agent is operational."""
        return self._circuit.is_available and self._backend.is_installed

    def process_command(self, user_text: str) -> str:
        """Process a voice command through the external AI CLI tool."""
        if not self._backend.is_installed:
            return "Agent unavailable (CLI tool not installed)"

        if not self._circuit.is_available:
            return "Agent temporarily unavailable (circuit breaker open)"

        result = self._circuit.call(
            self._route_command,
            user_text,
            fallback=lambda: "Agent temporarily unavailable",
        )
        return result or "No response from agent."

    def _route_command(self, user_text: str) -> str:
        """Use the CLI backend to interpret the command and route to a tool."""
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
        """Parse the CLI tool's JSON response and execute the matched command."""
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
