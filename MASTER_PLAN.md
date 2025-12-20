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

### Phase 1: Robust Wake Word (Complete)
**Goal:** Hands-free activation with minimal CPU usage (~1-2%).
- **Engine:** `openWakeWord` (hey_jarvis_v0.1.onnx).
- **Status:** ✅ Implemented.

### Phase 2: Dual-Path Routing (Complete)
**Goal:** Distinguish clearly between wanting to continuously dictate vs. wanting a quick answer.
- **Status:** ✅ Implemented (Unified Audio Stream State Machine).

### Phase 3: The Local Agent (Complete)
**Goal:** Smart reasoning on < 4GB RAM.
- **Engine:** `llama.cpp` (Qwen 2.5 1.5B).
- **Status:** ✅ Implemented with Native Tools:
    - **Web**: Open Browser/Search.
    - **System**: Volume/Brightness.
    - **Launcher**: App launching.
    - **Input**: Keyboard simulation.

### Phase 4: Continuous Mode (Complete)
**Goal:** Interactive "Agent Loop" for back-to-back commands.
- **Status:** ✅ Implemented (F10 / "Start Agent").

### Phase 5: Visual Interface (Complete)
**Goal:** Floating overlay for feedback.
- **Technology:** `tkinter`.
- **Status:** ✅ Implemented (Transparent Overlay).

---

## 4. Ease of Usage (User Experience)

### Installation
One-click setup for dependencies.
```bash
./install.sh  # Downloads models, setups venv & systemd
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
