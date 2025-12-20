import subprocess

def type_text(text):
    subprocess.run([
        "xdotool",
        "type",
        "--delay", "1",
        "--clearmodifiers",
        text
    ])

def backspace(n):
    if n <= 0:
        return
    # Correctly construct the command: one "xdotool key ..." with multiple "BackSpace" keys
    cmd = [
        "xdotool",
        "key",
        "--clearmodifiers"
    ] + ["BackSpace"] * n
    
    subprocess.run(cmd)
