"""AgentService: Orchestrates LLM inference and command execution with circuit breaker protection."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from dictator.agent.commands import CommandRegistry
from dictator.agent.sandbox import CommandSandbox
from dictator.core.models import ModelManager
from dictator.core.resilience import CircuitBreaker

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = (
    "You are Jarvis, a helpful voice assistant on {platform}. "
    "Use tools to fulfill requests. Be concise in responses."
)


class AgentService:
    """Orchestrates LLM-powered command processing with resilience.

    - Wraps LLM inference in a circuit breaker (trips after 3 failures)
    - Sanitizes LLM output before passing to command handlers
    - Enforces token limits on LLM input
    """

    def __init__(self, registry: CommandRegistry, model_manager: ModelManager):
        self._registry = registry
        self._sandbox = CommandSandbox(registry)
        self._model_manager = model_manager
        self._circuit = CircuitBreaker(name="llm_inference", failure_threshold=3, reset_timeout=60.0)
        self._platform = "Windows" if sys.platform == "win32" else "Linux"

    @property
    def is_available(self) -> bool:
        """Check if the agent is operational."""
        return self._circuit.is_available and self._model_manager.get_llm() is not None

    def process_command(self, user_text: str) -> str:
        """Process a voice command through the LLM agent."""
        if not self._circuit.is_available:
            return "Agent temporarily unavailable (circuit breaker open)"

        llm = self._model_manager.get_llm()
        if not llm:
            return "Agent offline (model not loaded)"

        result = self._circuit.call(
            self._run_inference,
            llm,
            user_text,
            fallback=lambda: "Agent temporarily unavailable",
        )
        return result or "No response from agent."

    def _run_inference(self, llm: Any, user_text: str) -> str:
        """Run the LLM inference and handle tool calls."""
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_TEMPLATE.format(platform=self._platform),
            },
            {"role": "user", "content": user_text[:2000]},  # Cap input length
        ]

        tools = self._registry.get_tool_schemas()

        response = llm.create_chat_completion(
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        choice = response["choices"][0]["message"]
        tool_calls = choice.get("tool_calls", [])

        if not tool_calls:
            content = choice.get("content", "")
            tool_calls = self._extract_tool_call_fallback(content) or []

        if not tool_calls:
            return choice.get("content", "No response.")

        return self._execute_tool_call(tool_calls[0])

    def _execute_tool_call(self, tool_call: dict) -> str:
        """Execute a single tool call through the sandbox."""
        fn_name = tool_call["function"]["name"]
        raw_args = tool_call["function"]["arguments"]

        try:
            fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            return f"Invalid arguments for {fn_name}"

        logger.info(f"Agent tool call: {fn_name}({fn_args})")
        return self._sandbox.execute(fn_name, fn_args)

    def _extract_tool_call_fallback(self, content: str) -> list[dict] | None:
        """Fallback parser for malformed Qwen tool-call output."""
        try:
            if "<tool_call>" in content:
                content = content.split("<tool_call>")[1].split("</tool_call>")[0]

            start_idx = content.find("{")
            if start_idx == -1:
                return None

            depth = 0
            in_quote = False
            escape = False
            end_idx = -1

            for i in range(start_idx, len(content)):
                char = content[i]
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if char == '"':
                    in_quote = not in_quote
                if not in_quote:
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break

            if end_idx == -1:
                raw = content[start_idx:] + "}" * depth
            else:
                raw = content[start_idx:end_idx]

            tool_data = json.loads(raw)

            return [
                {
                    "function": {
                        "name": tool_data["name"],
                        "arguments": json.dumps(tool_data.get("arguments", {})),
                    }
                }
            ]
        except (json.JSONDecodeError, KeyError, IndexError):
            return None
