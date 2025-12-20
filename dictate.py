from audio import start_stream
from transcriber import transcribe_loop, load_model, force_reset
from inject import type_text, backspace
from pynput import keyboard
import time
import sys

import argparse

# Global state
active = False
committed = ""

import subprocess

def notify(message):
    try:
        subprocess.run(["notify-send", "-u", "normal", "-i", "audio-input-microphone", "Dictator", message])
    except Exception:
        pass

def on_press(key):
    global active
    if key == keyboard.Key.f9:
        active = not active
        if active:
            force_reset()
        status = "ON 🔴" if active else "OFF ⚪"
        print(f"Dictation: {status}")
        notify(status)

import re

def clean_text(text):
    # Remove doubled words: "and and" -> "and", "see see" -> "see"
    # Case insensitive
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return text

def main():
    global committed, active
    
    parser = argparse.ArgumentParser(description="Dictator: Global Audio Typing Tool")
    parser.add_argument("--device", type=str, default=None, help="Audio input device index or name")
    parser.add_argument("--model", type=str, default="base.en", help="Whisper model size (tiny.en, base.en, small.en, medium.en)")
    parser.add_argument("--no-partial", action="store_true", help="Disable partial live updates (types only final sentences)")
    args = parser.parse_args()
    
    print("Initializing...")
    
    # Load model first
    load_model(args.model)
    
    if args.device is not None:
        print(f"Using Audio Device Index: {args.device}")
    
    print("Press F9 to toggle dictation.")

    # Start hotkey listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    # Audio stream context
    try:
        with start_stream(device_index=args.device):
            print("Audio stream started. Ready.")
            
            # Transcription loop
            for result in transcribe_loop():
                text, is_final = result
                
                if not active:
                    committed = "" 
                    continue
                
                if is_final:
                    # Finalized text:
                    text = clean_text(text)
                    
                    # 1. Backspace any PENDING partial text (committed)
                    if committed:
                        backspace(len(committed))
                        committed = ""
                    
                    # 2. Type the final text + space
                    if text:
                        type_text(text + " ")
                    
                else:
                    # Partial text update:
                    if args.no_partial:
                        continue
                        
                    text = clean_text(text) # Clean partials too? Yes, looks better.
                    
                    # 1. Backspace previous partial
                    if committed:
                        backspace(len(committed))
                    
                    # 2. Type new partial
                    if text:
                        type_text(text)
                    
                    # 3. Update active partial buffer
                    committed = text
                
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)

if __name__ == "__main__":
    main()
