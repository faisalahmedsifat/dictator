# Implementation Plan - Phase 1 & 2: Wake Word & Routing

This plan covers the implementation of the robust wake word listener and the basic dual-path routing logic defined in `MASTER_PLAN.md`.

## Goal
Establish a reliable, hands-free entry point for the assistant that distinguishes between "Dictation" (continuous typing) and "Agent" (single command) requests.

## User Review Required
> [!IMPORTANT]
> **Hardware Dependency**: Verification of `openWakeWord` performance on the user's specific CPU is needed. We assume standard Linux audio (PulseAudio/PipeWire) and `sounddevice` compatibility.

## Proposed Changes

### Core Logic (`dictation/`)
#### [NEW] [wake_listener.py](file:///home/faisal/Workspace/Dev/Personal/dictator/wake_listener.py)
- **Purpose**: Runs a dedicated thread/process to listen for "Hey Jarvis" using `openWakeWord`.
- **Key Features**:
    - Ring buffer audio capture (via `sounddevice`).
    - Low-latency detection loop.
    - Callback system to trigger the main coordinator.

#### [MODIFY] [dictate.py](file:///home/faisal/Workspace/Dev/Personal/dictator/dictate.py)
- **Purpose**: Refactor from a simple script to the main "Coordinator".
- **Changes**:
    - Integrate `wake_listener` import.
    - specialized logic to handle the `start_dictation` vs `agent_command` classification.
    - Implement the "Ding" sound effect playback on trigger.

### Audio Infrastructure
#### [MODIFY] [audio.py](file:///home/faisal/Workspace/Dev/Personal/dictator/audio.py)
- **Purpose**: unexpected issues with blocking I/O.
- **Changes**:
    - Ensure non-blocking recording capabilities for the wake word listener.
    - Add utility for playing the feedback chime (`play_chime()`).

## Verification Plan

### Automated Tests
- **Unit Tests**: Test the wake word loader and ring buffer logic.
- **Simulation**: Feed a pre-recorded WAV file containing "Hey Jarvis" into the listener to verify trigger event.

### Manual Verification
1.  **Start Service**: Run `dictate.py` (or the service wrapper).
2.  **Voice Test**:
    - Say "Hey Jarvis" -> Verify Chime + Log "Agent Mode Ready".
    - Say "Hey Jarvis, start dictation" -> Verify Chime + Log "Dictation Mode Started".
3.  **Resource Check**: Monitor `htop` to ensure CPU usage is < 5% while listening.

## Phase 3: The Smart Agent

**Technology Stack:**
- **Engine:** `llama-cpp-python` (Direct Integration).
- **Model:** `Qwen 2.5 1.5B Instruct` (GGUF).
- **Pattern:** Native Tool Calling with Grammar Sampling.

**Workflow:**
1.  **Input:** Router detects "Agent Command".
2.  **Inference:** Call `create_chat_completion` with tools.
3.  **Execution:** Parse JSON -> Execute Python Function.
4.  **Response:** Summarize/Display result.

**Tools:** Search, System Control, App Launcher.
