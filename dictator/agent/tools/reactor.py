"""ReactorCommand: Delegates complex tasks to the external Reactor agent with timeout and output cap."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any

from dictator.agent.commands import Command
from dictator.platform.interfaces import WindowContext

logger = logging.getLogger(__name__)

MAX_OUTPUT_LINES = 200
REACTOR_TIMEOUT = 120  # 2 minutes max


class ReactorCommand(Command):
    def __init__(self, window_context: WindowContext):
        self._window_ctx = window_context

    @property
    def name(self) -> str:
        return "ask_reactor"

    @property
    def description(self) -> str:
        return "Delegate a complex task (coding, research, planning) to the Reactor agent."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed description of the task for Reactor",
                },
                "project_dir": {
                    "type": "string",
                    "description": "Absolute path to the project directory",
                },
            },
            "required": ["prompt"],
        }

    def execute(self, args: dict[str, Any]) -> str:
        prompt = args.get("prompt", "")
        project_dir = args.get("project_dir")

        if not prompt:
            return "No prompt provided for Reactor."

        reactor_cmd = shutil.which("reactor")
        if not reactor_cmd:
            return "Error: 'reactor' not found in PATH."

        if not project_dir:
            pid = self._window_ctx.get_active_window_pid()
            if pid:
                project_dir = self._window_ctx.get_shell_cwd(pid)

        cmd = [reactor_cmd, "-p", prompt]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=project_dir,
                text=True,
                bufsize=1,
            )

            output_lines: list[str] = []
            for line in iter(process.stdout.readline, ""):  # type: ignore[union-attr]
                clean_line = line.strip()
                if clean_line:
                    output_lines.append(clean_line)
                    if len(output_lines) >= MAX_OUTPUT_LINES:
                        process.kill()
                        output_lines.append("[Output truncated at limit]")
                        break

            process.wait(timeout=REACTOR_TIMEOUT)

            if process.returncode != 0:
                return f"Reactor failed with code {process.returncode}"

            return "Reactor Output:\n" + "\n".join(output_lines[-50:])

        except subprocess.TimeoutExpired:
            process.kill()  # type: ignore[union-attr]
            return "Reactor timed out after 2 minutes."
        except FileNotFoundError:
            return f"Error: directory '{project_dir}' not found."
        except Exception as e:
            return f"Failed to call Reactor: {e}"
