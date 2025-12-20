from src.audio import start_stream, play_sound, fetch_audio
from src.transcriber import transcribe_loop, load_model, force_reset
from src.inject import type_text, backspace
from src.wake_listener import WakeWordListener
from src.agent import process_command
from src.ui import monitor
from pynput import keyboard
import time
import sys
import re
import argparse
import subprocess

# --- Config ---
ROUTING_DURATION = 4.0

class AppState:
    IDLE = 0
    ROUTING = 1
    DICTATING = 2
    AGENT_LOOP = 3

current_state = AppState.IDLE
exit_flag = False
committed = ""
manual_override = False

def notify(message):
    try:
        subprocess.run(["notify-send", "-u", "normal", "-i", "audio-input-microphone", "Dictator", message], check=False)
    except Exception:
        pass

def clean_text(text):
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return text

def on_key_press(key):
    global current_state, manual_override
    if key == keyboard.Key.f9:
        if current_state == AppState.DICTATING:
            print("[Hotkey] Stopping Dictation...")
            current_state = AppState.IDLE
            manual_override = False
            notify("Dictation Stopped (Idle)")
            play_sound("exit")
            force_reset()
        else:
            print("[Hotkey] Forcing Dictation Mode...")
            current_state = AppState.DICTATING
            manual_override = True
            notify("Dictation Started")
            manual_override = True
            notify("Dictation Started")
            play_sound("success") # Use default output
    elif key == keyboard.Key.f10:
        if current_state == AppState.AGENT_LOOP:
            print("[Hotkey] Stopping Agent Mode...")
            current_state = AppState.IDLE
            manual_override = False
            notify("Agent Mode Stopped")
            monitor.update_status("idle")
            monitor.update_text("Agent Paused")
            play_sound("exit")
            force_reset()
        else:
            print("[Hotkey] Forcing Agent Mode...")
            current_state = AppState.AGENT_LOOP
            manual_override = True
            notify("Agent Mode Started")
            monitor.update_status("agent")
            monitor.update_text("Agent Listening...")
            play_sound("success")
            force_reset()

def main():
    global current_state, exit_flag, committed
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--model", type=str, default="base.en")
    parser.add_argument("--no-partial", action="store_true")
    args = parser.parse_args()

    print("--- Dictator: Intelligent Agent ---")
    load_model(args.model)
    
    # Start Hotkey Listener
    # Start Hotkey Listener
    k_listener = keyboard.Listener(on_press=on_key_press)
    k_listener.start()
    
    # Start UI
    monitor.start()
    monitor.update_text("Dictator Ready (F9: Dictate, F10: Agent)")
    monitor.update_status("idle")
    
    # Initialize Wake Listener (No stream, just logic)
    wake_processor = WakeWordListener()
    
    print("Initializing Audio Stream...")
    # Open ONE unified stream
    try:
        with start_stream(device_index=args.device):
            print("Stream Active. Waiting for 'Hey Jarvis'...")
            
            # audio generator
            stream_iterator = fetch_audio()
            
            while not exit_flag:
                try:
                    
                    if current_state == AppState.IDLE:
                        # Process one chunk directly
                        chunk = next(stream_iterator)
                        
                        # Detect Wake Word
                        word = wake_processor.process_chunk(chunk)
                        
                        if word:
                            print(f"\n[Wake] Detected: {word}")
                            notify("Hey Jarvis!")
                            monitor.update_text("I'm listening...")
                            monitor.update_status("listening")
                            # Play chime (blocking output, but input buffers in queue)
                            play_sound("wake") 
                            
                            # Switch to Routing
                            current_state = AppState.ROUTING
                            monitor.update_status("listening")
                            force_reset() # Reset transcriber buffer
                    
                    elif current_state == AppState.ROUTING:
                        print(f"Routing... (Listening for {ROUTING_DURATION}s)")
                        start_t = time.time()
                        captured_text = ""
                        
                        # Consume stream via transcriber
                        # We pass the SAME iterator, so no audio lost
                        for result in transcribe_loop(stream=stream_iterator):
                            text, is_final = result
                            if text: monitor.update_text(text)
                            
                            # Check state override (F9 pressed during routing)
                            if current_state == AppState.DICTATING:
                                break

                            # Heartbeat/Timeout check
                            if time.time() - start_t > ROUTING_DURATION:
                                break
                            
                            if text is None:
                                continue
                                
                            if text is None:
                                continue
                                
                            captured_text = text
                            if text: monitor.update_text(text)
                            
                            # Optimization: Early exit
                            cmd_check = text.lower()
                            if "start dictation" in cmd_check or "dictate mode" in cmd_check:
                                break
                        
                        # Decide Intent
                        print(f"Routing Info: Phrase='{captured_text}'")
                        cmd = captured_text.lower().strip()
                        
                        if current_state == AppState.DICTATING:
                            pass # Already handled by override
                        # Heuristics:
                        elif any(k in cmd for k in ["dictat", "typing", "typ", "write this"]):
                            print("Intent: Dictation")
                            notify("Starting Dictation")
                            monitor.update_text("Dictating...")
                            monitor.update_status("listening")
                            play_sound("success")
                            current_state = AppState.DICTATING
                            force_reset() # Prevent "start typing" from leaking into dictation
                        elif any(k in cmd for k in ["start agent", "co-pilot", "copilot", "lets talk", "let's talk"]):
                            print("Intent: Continuous Agent")
                            print("Intent: Continuous Agent")
                            notify("Agent Mode: Listening...")
                            monitor.update_status("agent")
                            monitor.update_text("Ready for commands...")
                            play_sound("success")
                            current_state = AppState.AGENT_LOOP
                            force_reset()
                        elif cmd:
                            print(f"Intent: Agent (Command='{cmd}')")
                            notify(f"Agent: {cmd:.20}...")
                            
                            # Execute Agent
                            play_sound("success") # Acknowledge
                            monitor.update_status("processing")
                            response = process_command(cmd)
                            
                            print(f"Agent Response: {response}")
                            notify(f"Agent: {response}")
                            monitor.show_agent_response(response)
                            # TODO: TTS if response is short?
                            
                            current_state = AppState.IDLE
                            monitor.update_status("idle")
                            force_reset()
                        else:
                            # Silence
                            print("Intent: None (Silence)")
                            current_state = AppState.IDLE
                            monitor.update_status("idle")
                            monitor.update_text("...")
                            force_reset()

                    elif current_state == AppState.DICTATING:
                        print("State: DICTATING")
                        
                        for result in transcribe_loop(stream=stream_iterator):
                             if current_state != AppState.DICTATING:
                                 break
                             
                             text, is_final = result
                             if text: monitor.update_text(text)
                             if text is None: continue
                             
                             if is_final:
                                text = clean_text(text)
                                if committed:
                                    backspace(len(committed))
                                    committed = ""
                                if text:
                                    type_text(text + " ")
                             else:
                                if args.no_partial: continue
                                text = clean_text(text)
                                if committed: backspace(len(committed))
                                if text: type_text(text)
                                committed = text
                        
                        # Loop exited
                        committed = ""

                    elif current_state == AppState.AGENT_LOOP:
                        print("State: AGENT_LOOP")
                        
                        for result in transcribe_loop(stream=stream_iterator):
                             if current_state != AppState.AGENT_LOOP:
                                 break
                             
                             text, is_final = result
                             if text: monitor.update_text(text)
                             if text is None: continue
                             
                             if is_final:
                                 cmd = text.lower().strip()
                                 if not cmd: continue
                                 
                                 print(f"[Agent Loop] Command: '{cmd}'")
                                 
                                 # Exit Check
                                 if cmd in ["stop", "exit", "quit", "go to sleep", "close agent"]:
                                     print("State: IDLE")
                                     notify("Agent Sleeping")
                                     monitor.update_status("idle")
                                     monitor.update_text("Agent Sleeping")
                                     play_sound("exit") # Down tone
                                     current_state = AppState.IDLE
                                     force_reset()
                                     break
                                 
                                 # Execute
                                 notify(f"Processing: {cmd}")
                                 monitor.update_status("processing")
                                 response = process_command(cmd)
                                 print(f"[Agent Loop] Output: {response}")
                                 monitor.show_agent_response(str(response))
                                 play_sound("success") # Feedback for completion
                                 monitor.update_status("agent")
                                 force_reset() # Clear buffer for next command

                except StopIteration:
                    print("Audio Stream Ended Unexpectedly.")
                    break
                    
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
