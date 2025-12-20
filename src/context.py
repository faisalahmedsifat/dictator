
import subprocess
import re
import os
import psutil
from pathlib import Path

def get_active_window_id():
    try:
        return subprocess.check_output(["xdotool", "getactivewindow"], text=True).strip()
    except:
        return None

def get_active_window_pid(win_id):
    try:
        return int(subprocess.check_output(["xdotool", "getwindowpid", win_id], text=True).strip())
    except:
        return None

def get_active_window_title(win_id):
    try:
        return subprocess.check_output(["xdotool", "getwindowname", win_id], text=True).strip()
    except:
        return ""

def get_shell_cwd(pid):
    """
    Tries to find the CWD of the shell running inside the terminal process (pid).
    """
    try:
        parent = psutil.Process(pid)
        # Look for child processes that satisfy:
        # 1. Are shells (bash, zsh, fish)
        # 2. Are associated with a terminal (pts)
        children = parent.children(recursive=True)
        for child in children:
            if child.name() in ['bash', 'zsh', 'fish', 'sh']:
                return child.cwd()
        
        # Fallback: If no shell child found (maybe user is running a command directly),
        # return the terminal's own CWD (often ~)
        return parent.cwd()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

def find_project_in_workspace(project_name):
    """
    Searches for 'project_name' in common code directories.
    """
    # Expanded search list
    roots = [
        os.path.expanduser("~/Workspace"),
        os.path.expanduser("~/Projects"),
        os.path.expanduser("~/Dev"),
        os.path.expanduser("~/git"),
        os.path.expanduser("~") # Fallback to home (slow?) 
    ]
    
    # 1. Direct checks in roots
    for root in roots:
        if not os.path.exists(root): continue
        
        # Check direct subdirs of these roots first (Depth 1)
        target = os.path.join(root, project_name)
        if os.path.isdir(target):
            return target
            
        # Check Depth 2 (e.g. ~/Workspace/Dev/dictator)
        try:
            for item in os.listdir(root):
                sub_path = os.path.join(root, item)
                if os.path.isdir(sub_path):
                    target_sub = os.path.join(sub_path, project_name)
                    if os.path.isdir(target_sub):
                        return target_sub
        except:
            continue
            
    return None

def infer_project_context():
    """
    Infers context using PID + Title strategies.
    """
    win_id = get_active_window_id()
    if not win_id: return None
    
    title = get_active_window_title(win_id)
    pid = get_active_window_pid(win_id)
    
    print(f"[Context] Title: '{title}', PID: {pid}")

    # Strategy 1: Terminal CWD (Most Robust for "Where am I")
    # Identify if it is a terminal
    is_terminal = False
    terminals = ["gnome-terminal", "konsole", "alacritty", "kitty", "xterm", "terminator"]
    
    # Check process name
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name().lower()
        cmdline = " ".join(proc.cmdline()).lower()
        if any(t in proc_name or t in cmdline for t in terminals):
            is_terminal = True
    except:
        pass

    if is_terminal:
        cwd = get_shell_cwd(pid)
        if cwd:
            return cwd

    # Strategy 2: VS Code (Title-to-Path)
    if "Visual Studio Code" in title or "Code" in title:
        # Extract project name
        # "file.py - dictator - Visual Studio Code" -> "dictator"
        parts = title.split(" - ")
        for part in reversed(parts):
            if part in ["Visual Studio Code", "Code"]: continue
            # The part before name might be file, but if we scan backwards, 
            # the project name is usually the first non-brand string.
            # actually usually: [file] - [project] - [app]
            # so parts[-2] is project.
            if len(parts) >= 2:
                potential_name = parts[-2]
                path = find_project_in_workspace(potential_name)
                if path: return path
            break

    # Strategy 3: Regex Fallback on Title (for ssh or custom prompts)
    match = re.search(r"([~/][a-zA-Z0-9_\-/]+)", title)
    if match:
        p = match.group(1)
        return os.path.expanduser(p)
            
    return None

if __name__ == "__main__":
    print("Inferred:", infer_project_context())
