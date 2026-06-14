from __future__ import annotations

import os
import re
import subprocess

import psutil


def get_active_window_id() -> str | None:
    try:
        return subprocess.check_output(
            ["xdotool", "getactivewindow"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_active_window_pid(win_id: str) -> int | None:
    try:
        return int(
            subprocess.check_output(
                ["xdotool", "getwindowpid", win_id], text=True
            ).strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def get_active_window_title(win_id: str) -> str:
    try:
        return subprocess.check_output(
            ["xdotool", "getwindowname", win_id], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_shell_cwd(pid: int) -> str | None:
    """Find the CWD of the shell process inside a terminal."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            if child.name() in ("bash", "zsh", "fish", "sh"):
                return child.cwd()
        return parent.cwd()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def find_project_in_workspace(project_name: str) -> str | None:
    """Search common code directories for a project by name."""
    roots = [
        os.path.expanduser("~/Workspace"),
        os.path.expanduser("~/Projects"),
        os.path.expanduser("~/Dev"),
        os.path.expanduser("~/git"),
    ]

    for root in roots:
        if not os.path.exists(root):
            continue

        target = os.path.join(root, project_name)
        if os.path.isdir(target):
            return target

        try:
            for item in os.listdir(root):
                sub_path = os.path.join(root, item)
                if os.path.isdir(sub_path):
                    target_sub = os.path.join(sub_path, project_name)
                    if os.path.isdir(target_sub):
                        return target_sub
        except PermissionError:
            continue

    return None


TERMINAL_NAMES = (
    "gnome-terminal",
    "konsole",
    "alacritty",
    "kitty",
    "xterm",
    "terminator",
    "wezterm",
)


def infer_project_context() -> str | None:
    """Infer the current project directory from the active window."""
    win_id = get_active_window_id()
    if not win_id:
        return None

    title = get_active_window_title(win_id)
    pid = get_active_window_pid(win_id)

    print(f"[Context] Title: '{title}', PID: {pid}")

    # Strategy 1: Terminal CWD
    if pid:
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name().lower()
            cmdline = " ".join(proc.cmdline()).lower()
            if any(t in proc_name or t in cmdline for t in TERMINAL_NAMES):
                cwd = get_shell_cwd(pid)
                if cwd:
                    return cwd
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Strategy 2: VS Code title parsing
    if "Visual Studio Code" in title or "Code" in title:
        parts = title.split(" - ")
        if len(parts) >= 2:
            potential_name = parts[-2].strip()
            path = find_project_in_workspace(potential_name)
            if path:
                return path

    # Strategy 3: Regex fallback for paths in title
    match = re.search(r"([~/][a-zA-Z0-9_\-/]+)", title)
    if match:
        return os.path.expanduser(match.group(1))

    return None


if __name__ == "__main__":
    print("Inferred:", infer_project_context())
