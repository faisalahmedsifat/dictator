# Project Architecture Document: Dictator

## 1. Introduction

Dictator is a personal AI assistant for Linux, designed to provide global voice typing and intelligent system control. It aims to offer a fast, private, and capable hands-free interaction experience with the operating system, leveraging local AI models for speech-to-text and natural language understanding.

## 2. Problem Solved

Dictator addresses the need for an efficient and private voice-controlled interface on Linux. It solves the challenges of:

*   **Hands-free system interaction:** Allowing users to control their PC and type text without needing a keyboard or mouse.
*   **Privacy:** By utilizing entirely local AI models (Whisper for STT, Qwen for LLM, openWakeWord for wake word detection), it ensures that no audio or command data leaves the user's machine.
*   **Efficiency on older hardware:** The architecture is optimized to run effectively on systems with limited resources (e.g., < 4GB RAM for the LLM).
*   **Seamless mode switching:** Providing a fluid transition between continuous dictation and intelligent agent command execution.

## 3. Creative Aspects

*   **Local-First AI Integration:** A key creative aspect is the successful integration of multiple powerful AI models (Whisper, Qwen, openWakeWord) to run entirely locally, offering a private and responsive user experience without reliance on cloud APIs.
*   **Unified Audio Stream & Coordinator Loop:** The design employs a single, unified audio stream processed by a central coordinator loop, which efficiently handles wake word detection, audio buffering, and routing to the appropriate AI engine (Dictation or Agent).
*   **Floating Visual Interface:** A transparent, always-on-top overlay provides real-time visual feedback to the user, showing live transcription and system status (Idle, Dictating, Agent Processing).
*   **Native Tool Calling with LLM:** The Qwen LLM is integrated with a robust tool-calling mechanism, allowing it to execute native Linux commands for system control, application launching, web searches, and keyboard simulation.

## 4. High-Level Architecture

The Dictator system operates as a background service, with a central `dictate.py` script acting as the **Coordinator**. This coordinator manages the audio input stream, listens for wake words, and routes user intent to specialized modules. A visual UI (`src/ui.py`) provides real-time feedback.

```mermaid
graph TD
    A[User Voice Input] --> B[Audio Stream (src/audio.py)];
    B --> C{Coordinator (dictate.py)};
    C --C -- Wake Word Detected (src/wake_listener.py) --> D{Intent Routing}; 
    C -- Hotkey (F9/F10) --> D{Intent Routing}; 
    D -- "Start Dictation" --> E[Dictation Engine (faster-whisper)];
    D -- "Agent Command" --> F[Smart Agent (llama-cpp-python)];
    E --> G[Keyboard Input (pynput)];
    F --> H[Tool Execution (e.g., Web Search, System Control)];
    E -- Transcription --> I[Visual UI (src/ui.py)];
    F -- Agent Response --> I[Visual UI (src/ui.py)];
    G --> J[Application/OS];
    H --> J[Application/OS];
    I --> A;
```

## 5. Low-Level Architecture & Key Components

### 5.1. `src/audio.py`
*   **Purpose:** Handles all audio input/output operations.
*   **Key Features:**
    *   Manages `sounddevice` for microphone input.
    *   Provides a ring buffer for efficient audio capture.
    *   Includes utilities for playing feedback chimes (`play_chime()`).
    *   Ensures non-blocking audio recording for continuous listening.

### 5.2. `src/wake_listener.py`
*   **Purpose:** Dedicated module for wake word detection.
*   **Key Features:**
    *   Utilizes `openWakeWord` with the `hey_jarvis_v0.1.onnx` model.
    *   Runs in a separate thread/process to minimize latency.
    *   Triggers a callback in the Coordinator upon wake word detection.
    *   Low CPU usage (~1-2%).

### 5.3. `dictate.py` (The Coordinator)
*   **Purpose:** The central orchestrator of the Dictator application.
*   **Key Features:**
    *   Initializes and manages the audio stream.
    *   Integrates `wake_listener` and processes its callbacks.
    *   Implements the "Dual-Path Routing" logic:
        *   Distinguishes between "Dictation Mode" (continuous typing) and "Agent Mode" (single command).
        *   Routes audio segments to either `faster-whisper` or `llama-cpp-python` based on intent.
    *   Manages the state of the visual UI.
    *   Handles global hotkey inputs (F9 for Dictation, F10 for Agent).

### 5.4. `src/stt.py` (Dictation Engine)
*   **Purpose:** Provides high-speed, accurate speech-to-text for dictation.
*   **Key Features:**
    *   Uses `faster-whisper` for real-time transcription.
    *   Processes continuous audio streams.
    *   Outputs transcribed text directly to the active window via `pynput`.

### 5.5. `src/agent.py` (Smart Agent)
*   **Purpose:** The intelligent reasoning and command execution module.
*   **Key Features:**
    *   Integrates `llama-cpp-python` with the `Qwen 2.5 1.5B Instruct` GGUF model.
    *   Performs natural language understanding and intent recognition.
    *   **Native Tool Calling:** Executes Python functions mapped to specific commands:
        *   **Web Tools:** Open browser, perform web searches.
        *   **System Control:** Adjust volume, brightness, etc.
        *   **App Launcher:** Launch applications.
        *   **Input Simulation:** Simulate keyboard presses (`pynput`).
    *   Generates visual and/or auditory responses to user commands.

### 5.6. `src/ui.py` (Visual Interface)
*   **Purpose:** Provides real-time visual feedback to the user.
*   **Key Features:**
    *   A transparent, always-on-top `tkinter` overlay.
    *   Displays live transcription during dictation.
    *   Shows status indicators (Idle, Dictating, Agent Processing).
    *   Communicates agent responses and system messages.

### 5.7. `src/context.py`
*   **Purpose:** Infers the current working context of the user.
*   **Key Features:**
    *   Uses `xdotool` and `psutil` to get active window information (ID, PID, Title).
    *   **Strategies for Context Inference:**
        *   **Terminal CWD:** Determines the current working directory of active shell processes.
        *   **VS Code Title-to-Path:** Extracts project names from VS Code window titles and maps them to local project paths.
        *   **Regex Fallback:** Uses regex to extract potential file paths or project names from generic window titles.
    *   Crucial for enabling context-aware commands (e.g., "open this file").

## 6. Data Flow

1.  **Audio Input:** Microphone captures user's voice.
2.  **Audio Stream:** `src/audio.py` continuously buffers audio.
3.  **Wake Word Detection:** `src/wake_listener.py` monitors the audio stream for "Hey Jarvis".
4.  **Coordinator Activation:** Upon wake word detection or hotkey press, `dictate.py` is activated.
5.  **Intent Routing:** The Coordinator analyzes the subsequent speech to determine if it's a "Dictation" request or an "Agent Command".
6.  **Dictation Mode:** If dictation, audio is sent to `src/stt.py` (`faster-whisper`), transcribed, and typed via `pynput`.
7.  **Agent Mode:** If an agent command, audio is sent to `src/agent.py` (`llama-cpp-python`).
8.  **LLM Processing:** The LLM processes the command, identifies intent, and determines if a tool call is needed.
9.  **Tool Execution:** If a tool is identified, `src/agent.py` executes the corresponding native Python function (e.g., `subprocess` for app launch, `pulsectl` for volume).
10. **Feedback:** Both modes provide real-time visual feedback through `src/ui.py` (transcription, agent responses, status).

## 7. Conclusion

Dictator provides a robust, private, and efficient voice-controlled interface for Linux. Its modular architecture, local AI integration, and intelligent routing system enable a seamless user experience for both continuous dictation and complex system control. The project is well-positioned for future enhancements, such as deeper system integration and more sophisticated context awareness.

