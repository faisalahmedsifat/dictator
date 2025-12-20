# Dictator: The Intelligent Local Assistant - Master Plan

## 1. Vision
Transform the simple dictation tool into a personal, privacy-first AI assistant optimized for older hardware. The system features two seamless modes: **High-Speed Dictation** and a **Smart Reasoning Agent**.

## 2. Architecture Overview

### The "Coordinator" loop
The application runs a low-latency loop monitoring audio for specific trigger phrases (Wake Words).

| Trigger | Mode | Underlying Engine |
| :--- | :--- | :--- |
| **"Hey Jarvis"** | **Agent Mode** (Command/Chat) | `llama.cpp` (Qwen 2.5 1.5B) |
| **"Hey Jarvis, start dictation"** | **Dictation Mode** (Continuous) | `faster-whisper` (Streaming) |
| **Global Hotkey (e.g., F9)** | **Dictation Mode** (Push-to-Talk) | `faster-whisper` (Streaming) |

---

## 3. Implementation Roadmap

### Phase 1: Robust Wake Word (Current Focus)
**Goal:** Hands-free activation with minimal CPU usage (~1-2%).
- **Engine:** `openWakeWord`
- **Model:** Pre-trained `hey_jarvis`.
- **Logic:**
    - Listen on Mic (Ring Buffer).
    - If "Hey Jarvis" detected -> Play Chime.
    - Start recording for Intent Classification.

### Phase 2: Dual-Path Routing & Differentiated Modes
**Goal:** Distinguish clearly between wanting to continuously dictate vs. wanting a quick answer.
- **Logic:**
    - **Wake Word ("Hey Jarvis")**:
        - Listens for "Start dictation" -> **Enter Continuous Dictation Mode**.
        - Else -> **Agent Mode** (Process single command).
    - **Global Hotkey**:
        - Immediately activates **Dictation Mode** while held (or toggled).

### Phase 3: The Local Agent
**Goal:** Smart reasoning on < 4GB RAM.
- **Engine:** `llama.cpp` (via `llama-cpp-python`).
- **Model:** `Qwen 2.5 1.5B` (Best for Tools).
- **Architecture:** Native Tool Calling with Grammar Sampling (No extra frameworks).
- **Capabilities**:
    - **Conversation**: Chat with the user.
    - **Tools**:
        - **Web**: Search Google/YouTube.
        - **System**: Real Volume/Brightness Control (`pulsectl`).
        - **Launcher**: Open Apps (`subprocess`).
        - **Input**: Simulate Keystrokes (`pynput`).

---

## 4. Ease of Usage (User Experience)

### Installation
One-click setup for dependencies.
```bash
./install.sh  # Includes models
```

### Daily Usage
1.  **Start**: Run `dictator` (Background service).
2.  **Activating**:
    - *User*: "Hey Jarvis, start dictation." -> *System*: "Ding!" -> *User*: "Hello world" -> *System*: Types "Hello world".
    - *User*: "Hey Jarvis, set volume to 50%." -> *System*: "Ding!" ... "Volume set to 50%."

---

## 5. Technical Stack Summary

| Component | Library | Reason |
| :--- | :--- | :--- |
| **Wake Word** | `openWakeWord` | Pre-trained, Offline, Fast |
| **STT (Dictation)** | `faster-whisper` | Accurate, Real-time |
| **LLM (Agent)** | `llama-cpp-python` | Max performance, Native Tool Calling |
| **Orchestrator** | Python Native | Zero-latency, Minimal footprint |
| **Audio I/O** | `sounddevice` | Reliable cross-platform audio |

## Next Step
- **Enhancement**: Explore clipboard intelligence and detailed system stats.
