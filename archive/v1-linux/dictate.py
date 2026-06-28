"""Dictator - Local voice assistant for Linux."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from enum import IntEnum

from pynput.keyboard import GlobalHotKeys

from src.audio import fetch_audio, play_sound, start_stream
from src.transcriber import force_reset, load_model, transcribe_loop
from src.inject import backspace, type_text
from src.wake_listener import WakeWordListener
from src.agent import process_command
from src.ui import monitor

ROUTING_DURATION = 4.0

DICTATION_KEYWORDS = ("dictat", "typing", "typ", "write this")
AGENT_KEYWORDS = ("start agent", "co-pilot", "copilot", "lets talk", "let's talk")
EXIT_COMMANDS = ("stop", "exit", "quit", "go to sleep", "close agent")


class State(IntEnum):
    IDLE = 0
    ROUTING = 1
    DICTATING = 2
    AGENT_LOOP = 3


current_state = State.IDLE
exit_flag = False
committed = ""


def notify(message: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "-u", "normal", "-i", "audio-input-microphone", "Dictator", message],
            check=False,
        )
    except FileNotFoundError:
        pass


def clean_text(text: str) -> str:
    """Remove repeated consecutive words."""
    return re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)


def toggle_dictation() -> None:
    global current_state
    if current_state == State.DICTATING:
        print("[Hotkey] Stopping dictation")
        current_state = State.IDLE
        notify("Dictation Stopped")
        play_sound("exit")
        force_reset()
    else:
        print("[Hotkey] Starting dictation")
        current_state = State.DICTATING
        notify("Dictation Started")
        play_sound("success")


def toggle_agent() -> None:
    global current_state
    if current_state == State.AGENT_LOOP:
        print("[Hotkey] Stopping agent")
        current_state = State.IDLE
        notify("Agent Stopped")
        monitor.update_status("idle")
        monitor.update_text("Agent Paused")
        play_sound("exit")
        force_reset()
    else:
        print("[Hotkey] Starting agent")
        current_state = State.AGENT_LOOP
        notify("Agent Started")
        monitor.update_status("agent")
        monitor.update_text("Agent Listening...")
        play_sound("success")
        force_reset()


def toggle_ui() -> None:
    monitor.toggle()


def toggle_log() -> None:
    monitor.toggle_log()


def hide_all() -> None:
    monitor.hide_all()


def handle_routing(stream_iterator) -> None:
    """Listen for a few seconds and classify intent."""
    global current_state, committed

    print(f"[Routing] Listening for {ROUTING_DURATION}s...")
    start_t = time.time()
    captured_text = ""

    for result in transcribe_loop(stream=stream_iterator):
        text, is_final = result
        if text:
            monitor.update_text(text)

        if current_state == State.DICTATING:
            break

        if time.time() - start_t > ROUTING_DURATION:
            break

        if text is None:
            continue

        captured_text = text

        cmd_check = text.lower()
        if "start dictation" in cmd_check or "dictate mode" in cmd_check:
            break

    print(f"[Routing] Captured: '{captured_text}'")
    cmd = captured_text.lower().strip()

    if current_state == State.DICTATING:
        return

    if any(k in cmd for k in DICTATION_KEYWORDS):
        print("[Routing] Intent: dictation")
        notify("Starting Dictation")
        monitor.update_text("Dictating...")
        monitor.update_status("listening")
        play_sound("success")
        current_state = State.DICTATING
        force_reset()

    elif any(k in cmd for k in AGENT_KEYWORDS):
        print("[Routing] Intent: agent loop")
        notify("Agent Mode")
        monitor.update_status("agent")
        monitor.update_text("Ready for commands...")
        play_sound("success")
        current_state = State.AGENT_LOOP
        force_reset()

    elif cmd:
        print(f"[Routing] Intent: one-shot command '{cmd}'")
        monitor.update_log(f"User: {cmd}")
        play_sound("success")
        monitor.update_status("processing")

        response = process_command(cmd)
        print(f"[Agent] Response: {response}")
        monitor.show_agent_response(response)

        current_state = State.IDLE
        monitor.update_status("idle")
        force_reset()
    else:
        print("[Routing] Intent: none (silence)")
        current_state = State.IDLE
        monitor.update_status("idle")
        monitor.update_text("...")
        force_reset()


def handle_dictation(stream_iterator, no_partial: bool) -> None:
    """Continuous voice-to-text dictation."""
    global current_state, committed

    print("[State] DICTATING")

    for result in transcribe_loop(stream=stream_iterator):
        if current_state != State.DICTATING:
            break

        text, is_final = result
        if text:
            monitor.update_text(text)
        if text is None:
            continue

        if is_final:
            text = clean_text(text)
            if committed:
                backspace(len(committed))
                committed = ""
            if text:
                type_text(text + " ")
        else:
            if no_partial:
                continue
            text = clean_text(text)
            if committed:
                backspace(len(committed))
            if text:
                type_text(text)
            committed = text

    committed = ""


def handle_agent_loop(stream_iterator) -> None:
    """Continuous agent command loop."""
    global current_state

    print("[State] AGENT_LOOP")

    for result in transcribe_loop(stream=stream_iterator):
        if current_state != State.AGENT_LOOP:
            break

        text, is_final = result
        if text:
            monitor.update_text(text)
        if text is None:
            continue

        if not is_final:
            continue

        cmd = text.lower().strip()
        if not cmd:
            continue

        print(f"[Agent Loop] Command: '{cmd}'")
        monitor.update_log(f"User: {cmd}")

        if cmd in EXIT_COMMANDS:
            print("[Agent Loop] Exiting")
            notify("Agent Sleeping")
            monitor.update_status("idle")
            monitor.update_text("Agent Sleeping")
            play_sound("exit")
            current_state = State.IDLE
            force_reset()
            break

        monitor.update_status("processing")
        response = process_command(cmd)
        print(f"[Agent Loop] Response: {response}")
        monitor.show_agent_response(str(response))
        play_sound("success")
        monitor.update_status("agent")
        force_reset()


def main() -> None:
    global current_state, exit_flag

    parser = argparse.ArgumentParser(description="Dictator - Voice Assistant for Linux")
    parser.add_argument("--device", type=str, default=None, help="Mic device name or index")
    parser.add_argument("--model", type=str, default="base.en", help="Whisper model size")
    parser.add_argument("--no-partial", action="store_true", help="Disable live partial typing")
    args = parser.parse_args()

    print("--- Dictator: Voice Assistant ---")
    load_model(args.model)

    hotkeys = GlobalHotKeys({
        "<f9>": toggle_dictation,
        "<f10>": toggle_agent,
        "<ctrl>+<space>": toggle_ui,
        "<ctrl>+<alt>+<enter>": toggle_log,
        "<ctrl>+<shift>+<enter>": hide_all,
    })
    hotkeys.start()

    monitor.start()
    monitor.update_text("Dictator Ready (F9: Dictate, F10: Agent)")
    monitor.update_status("idle")

    wake_processor = WakeWordListener()

    print("[Init] Starting audio stream...")
    try:
        with start_stream(device_index=args.device):
            print("[Init] Stream active. Waiting for 'Hey Jarvis'...")
            stream_iterator = fetch_audio()

            while not exit_flag:
                try:
                    if current_state == State.IDLE:
                        chunk = next(stream_iterator)
                        word = wake_processor.process_chunk(chunk)

                        if word:
                            print(f"\n[Wake] Detected: {word}")
                            monitor.update_text("I'm listening...")
                            monitor.update_status("listening")
                            play_sound("wake")
                            current_state = State.ROUTING
                            force_reset()

                    elif current_state == State.ROUTING:
                        handle_routing(stream_iterator)

                    elif current_state == State.DICTATING:
                        handle_dictation(stream_iterator, args.no_partial)

                    elif current_state == State.AGENT_LOOP:
                        handle_agent_loop(stream_iterator)

                except StopIteration:
                    print("[Error] Audio stream ended unexpectedly.")
                    break

    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"[Fatal] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
