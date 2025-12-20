
import json
import subprocess
import webbrowser
import sys
import shutil
import pulsectl
import warnings
import time
from pynput.keyboard import Controller, Key
from llama_cpp import Llama

# --- Tools Definition ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_browser",
            "description": "Open a web browser, optionally searching for a query or opening a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the browser (e.g. chrome, firefox)", "default": "default"},
                    "search_query": {"type": "string", "description": "Text to search for"},
                    "url": {"type": "string", "description": "Direct URL to open"}
                },
                "required": [] 
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "Control system settings like volume or brightness",
            "parameters": {
                "type": "object",
                "properties": {
                    "setting": {"type": "string", "enum": ["volume", "brightness"]},
                    "action": {"type": "string", "enum": ["up", "down", "mute", "set"]},
                    "value": {"type": "integer", "description": "Percentage value (0-100)"}
                },
                "required": ["setting", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "app_launcher",
            "description": "Launch a desktop application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the application (e.g. code, spotify, terminal)"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_keys",
            "description": "Simulate keyboard key presses or text typing",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Key combo (e.g. 'ctrl+c', 'alt+enter') or text"}
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_reactor",
            "description": "Delegate a complex task (coding, research, planning) to the 'Reactor' Super-Agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Detailed description of the task for Reactor"},
                    "project_dir": {"type": "string", "description": "Absolute path to the project directory where Reactor should work. Defaults to current directory."}
                },
                "required": ["prompt"]
            }
        }
    }
]

# --- Global Model Instance ---
llm = None
MODEL_PATH = "src/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"

def load_agent():
    global llm
    if llm is None:
        print("[Agent] Loading Qwen Model...")
        try:
            llm = Llama(
                model_path=MODEL_PATH,
                n_gpu_layers=-1, 
                n_ctx=4096,
                verbose=False
            )
            print("[Agent] Model Loaded.")
        except Exception as e:
            print(f"[Agent] Error loading model: {e}")

# --- Tool Implementations ---
def handle_open_browser(args):
    query = args.get("search_query")
    url = args.get("url")
    app = args.get("app_name", "default").lower()
    
    target_url = url
    
    # 1. Handle Known Apps / Sites
    if "youtube" in app:
        if query:
            target_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        else:
            target_url = "https://www.youtube.com"
    elif "google" in app and not target_url:
        target_url = "https://www.google.com"

    # 2. General Search Fallback
    if not target_url:
        if query:
            target_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        else:
            # Fallback to homepage
            target_url = "https://www.google.com"
    
    print(f"[Tool] Opening Browser: {target_url}")
    
    # Linux specific open
    try:
        webbrowser.open(target_url)
        return f"Opened {app}: {query if query else target_url}"
    except Exception as e:
        return f"Failed to open browser: {e}"

def handle_system_control(args):
    setting = args.get("setting")
    action = args.get("action")
    value = args.get("value", 10) # Default step 10%
    
    msg = ""
    try:
        if setting == "volume":
            with pulsectl.Pulse('dictator-agent') as pulse:
                # Get default sink
                sink = pulse.server_info().default_sink_name
                sink_info = pulse.get_sink_by_name(sink)
                
                curr_vol = sink_info.volume.value_flat
                
                new_vol = curr_vol
                if action == "up":
                    new_vol = min(1.0, curr_vol + (value / 100))
                elif action == "down":
                    new_vol = max(0.0, curr_vol - (value / 100))
                elif action == "mute":
                     pulse.mute(sink_info, not sink_info.mute)
                     return "Mute toggled."
                elif action == "set":
                    new_vol = min(1.0, max(0.0, value / 100))
                
                pulse.volume_set_all_chans(sink_info, new_vol)
                msg = f"Volume set to {int(new_vol * 100)}%"
        else:
             msg = f"Setting '{setting}' not yet implemented."
             
    except Exception as e:
        msg = f"Error controlling system: {e}"
        
    return msg

def handle_app_launcher(args):
    app = args.get("app_name", "").lower()
    if not app: return "No app name provided."
    
    # Map common names
    cmd = app
    if "code" in app or "vscode" in app: cmd = "code"
    elif "chrome" in app: cmd = "google-chrome"
    elif "terminal" in app: cmd = "gnome-terminal"
    elif "spotify" in app: cmd = "spotify"
    
    if not shutil.which(cmd):
        return f"App '{cmd}' not found in PATH."
        
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Launched {cmd}"
    except Exception as e:
        return f"Failed to launch {cmd}: {e}"

def handle_simulate_keys(args):
    keys_str = args.get("keys", "").lower()
    # Clean quotes if model added them inside the string
    keys_str = keys_str.replace("'", "").replace('"', "")
    
    if not keys_str: return "No keys provided."
    
    keyboard = Controller()
    
    msg = ""
    try:
        # Handle Combos
        if "+" in keys_str:
            keys = keys_str.split("+")
            
            # Map robustly key strings to Key objects
            py_keys = []
            for k in keys:
                k = k.strip()
                if hasattr(Key, k):
                    py_keys.append(getattr(Key, k))
                else:
                    py_keys.append(k) # Character
            
            # Press all in order
            for k in py_keys:
                keyboard.press(k)
                
            time.sleep(0.05)
            
            # Release in reverse
            for k in reversed(py_keys):
                keyboard.release(k)
                
            msg = f"Pressed combo: {keys_str}"
        else:
            # Single special key or typing?
            # Heuristic: if it's a special key name, press it. Else type it.
            if hasattr(Key, keys_str):
                k = getattr(Key, keys_str)
                keyboard.press(k)
                keyboard.release(k)
                msg = f"Pressed key: {keys_str}"
            else:
                keyboard.type(keys_str)
                msg = f"Typed: {keys_str}"
                
    except Exception as e:
        msg = f"Failed to simulate keys: {e}"
        
    return msg

# Lazy import to avoid circular dep or heavy load on init
def handle_ask_reactor(args):
    from src.context import infer_project_context
    from src.ui import monitor

    prompt = args.get("prompt", "")
    project_dir = args.get("project_dir", None)
    
    if not prompt: return "No prompt provided for Reactor."
    
    # Auto-infer context if missing
    if not project_dir:
        print("[Tool] No project_dir provided. Inferring from context...")
        project_dir = infer_project_context()
        if project_dir:
            print(f"[Tool] Inferred Project Path: {project_dir}")
    
    msg = f"[Tool] Asking Reactor: '{prompt}'"
    if project_dir:
        msg += f" (in {project_dir})"
    print(msg)
    monitor.update_log(f"Reactor: {prompt}")
    
    # Check if reactor exists
    if not shutil.which("reactor"):
        # Fallback for user's miniconda path if mostly static
        reactor_path = "/home/faisal/miniconda3/bin/reactor"
        if not shutil.which(reactor_path):
             return "Error: 'reactor' tool not found in PATH."
        cmd = [reactor_path, "-p", prompt]
    else:
        cmd = ["reactor", "-p", prompt]

    try:
        # Run with Popen for streaming
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=project_dir,
            text=True,
            bufsize=1
        )
        
        full_output = []
        for line in iter(process.stdout.readline, ''):
            clean_line = line.strip()
            if clean_line:
                print(f"[Reactor] {clean_line}")
                monitor.update_log(clean_line)
                full_output.append(clean_line)
        
        process.wait()
        
        if process.returncode != 0:
            return f"Reactor failed with code {process.returncode}"
        
        return f"Reactor Output:\n" + "\n".join(full_output)
        
    except FileNotFoundError:
        return f"Error: Project directory '{project_dir}' not found."
    except Exception as e:
        return f"Failed to call Reactor: {e}"


# --- Main Entry Point ---
def process_command(user_text):
    load_agent()
    if not llm:
        return "Agent Offline"
        
    messages = [
        {"role": "system", "content": "You are Jarvis, a helpful assistant on Linux. Use tools to fulfill requests."},
        {"role": "user", "content": user_text}
    ]
    
    # 1. Inference
    response = llm.create_chat_completion(
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    choice = response["choices"][0]["message"]
    
    # 2. Check for Tool Calls
    tool_calls = choice.get("tool_calls", [])
    
    # FALLBACK: Robust JSON Extractor
    if not tool_calls and ("<tool_call>" in choice["content"] or "{" in choice["content"]):
        try:
            content = choice["content"]
            # Remove XML wrappers if present
            if "<tool_call>" in content:
                content = content.split("<tool_call>")[1].split("</tool_call>")[0]
            
            # Robust Extraction Logic
            # 1. Find first '{'
            start_idx = content.find("{")
            if start_idx == -1: raise Exception("No JSON start found.")
            
            # 2. Track balance to find end
            depth = 0
            in_quote = False
            end_idx = -1
            escape = False
            
            for i in range(start_idx, len(content)):
                char = content[i]
                
                if escape:
                    escape = False
                    continue
                    
                if char == '\\':
                    escape = True
                    continue
                
                if char == '"':
                    in_quote = not in_quote
                
                if not in_quote:
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
            
            if end_idx == -1:
                # If we couldn't find a clean end, try minimal repair (append })
                # But usually this means malformed. Let's try to parse what we have + '}'
                raw_extracted = content[start_idx:] + "}" * depth
            else:
                raw_extracted = content[start_idx:end_idx]

            print(f"[Debug] Extracted JSON: '{raw_extracted}'")
            
            # 3. Parse and Unpack
            # We accept the Qwen format which is often double-bracketed {{...}}
            try:
                # Try direct load first
                tool_data = json.loads(raw_extracted)
            except:
                # Fallback: Find the widest outer braces, then drill down
                # Sometimes raw_extracted has tail garbage
                s_idx = raw_extracted.find("{")
                e_idx = raw_extracted.rfind("}")
                
                if s_idx != -1 and e_idx != -1:
                    candidate = raw_extracted[s_idx:e_idx+1]
                    # Loop to strip layers of braces until valid
                    # Max 3 layers to prevent infinite loops
                    for _ in range(3):
                        try:
                            tool_data = json.loads(candidate)
                            break
                        except:
                            # If it starts/ends with braces, strip them
                            if candidate.startswith("{") and candidate.endswith("}"):
                                candidate = candidate[1:-1].strip()
                            else:
                                raise
                    else:
                        # loop exhausted
                        raise
                else:
                    raise

            tool_calls = [{
                "function": {
                    "name": tool_data["name"],
                    "arguments": json.dumps(tool_data["arguments"])
                }
            }]
        except Exception as e:
            print(f"[Agent] Failed to parse raw tool call: {e}")

    if tool_calls:
        t_call = tool_calls[0]
        fn_name = t_call["function"]["name"]
        raw_args = t_call["function"]["arguments"]
        fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        
        print(f"[Agent] Call: {fn_name}({fn_args})")
        
        result = ""
        if fn_name == "open_browser":
            result = handle_open_browser(fn_args)
        elif fn_name == "system_control":
            result = handle_system_control(fn_args)
        elif fn_name == "app_launcher":
            result = handle_app_launcher(fn_args)
        elif fn_name == "simulate_keys":
            result = handle_simulate_keys(fn_args)
        elif fn_name == "ask_reactor":
            result = handle_ask_reactor(fn_args)
        else:
            result = "Error: Unknown tool."
            
        print(f"[Tool Output] {result}")
        return result
    else:
        # Direct response
        return choice["content"]

if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        print(process_command(sys.argv[1]))
    else:
        print(process_command("Search for cute cats"))
