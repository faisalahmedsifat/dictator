from __future__ import annotations

import queue

import numpy as np
import sounddevice as sd
from scipy import signal

TARGET_RATE = 16000
BLOCK_DURATION = 0.2

audio_queue: queue.Queue[np.ndarray] = queue.Queue()
current_native_rate: int = 16000


def _resolve_device(device_index: str | int | None) -> int | None:
    """Resolve a device name or string index to an integer device index."""
    if device_index is None:
        return None

    if isinstance(device_index, int):
        return device_index

    try:
        return int(device_index)
    except ValueError:
        pass

    devices = sd.query_devices()
    target = device_index

    for i, dev in enumerate(devices):
        if dev["name"] == target and dev["max_input_channels"] > 0:
            return i

    for i, dev in enumerate(devices):
        if target in dev["name"] and dev["max_input_channels"] > 0:
            print(f"[Audio] Resolved '{target}' -> index {i} ({dev['name']})")
            return i

    raise ValueError(f"Could not find input device matching: {device_index}")


def start_stream(device_index: str | int | None = None) -> sd.InputStream:
    global current_native_rate

    resolved = _resolve_device(device_index)

    if resolved is not None:
        info = sd.query_devices(resolved, "input")
    else:
        info = sd.query_devices(kind="input")

    native_rate = int(info["default_samplerate"])
    current_native_rate = native_rate
    block_size = int(native_rate * BLOCK_DURATION)

    def audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            print(f"[Audio] {status}")
        audio_queue.put(indata.copy())

    print(f"[Audio] Opening stream: device={resolved}, rate={native_rate}Hz")

    with audio_queue.mutex:
        audio_queue.queue.clear()

    return sd.InputStream(
        device=resolved,
        samplerate=native_rate,
        channels=1,
        blocksize=block_size,
        callback=audio_callback,
        dtype=np.float32,
    )


def fetch_audio():
    """Generator yielding resampled 16kHz float32 chunks from the queue."""
    while True:
        raw_chunk = audio_queue.get()

        if current_native_rate != TARGET_RATE:
            num_samples = int(len(raw_chunk) * TARGET_RATE / current_native_rate)
            yield signal.resample(raw_chunk, num_samples).astype(np.float32)
        else:
            yield raw_chunk


def play_sound(style: str = "wake") -> None:
    """Play synthetic feedback sounds (wake/success/exit)."""
    fs = 44100

    if style == "wake":
        duration = 0.2
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        envelope = np.concatenate([
            np.linspace(0, 1, int(fs * 0.05)),
            np.ones(int(fs * 0.1)),
            np.linspace(1, 0, int(fs * 0.05)),
        ])
        wave = 0.5 * np.sin(2 * np.pi * 880.0 * t) * envelope

    elif style == "success":
        duration = 0.3
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        len_note = len(t) // 2
        t1, t2 = t[:len_note], t[len_note:]

        wave1 = 0.5 * np.sin(2 * np.pi * 880.0 * t1)
        wave2 = 0.5 * np.sin(2 * np.pi * 1108.0 * t2)

        env1 = np.concatenate([
            np.linspace(0, 1, int(fs * 0.02)),
            np.linspace(1, 0, len_note - int(fs * 0.02)),
        ])
        env2 = np.concatenate([
            np.linspace(0, 1, int(fs * 0.02)),
            np.linspace(1, 0, len(t2) - int(fs * 0.02)),
        ])

        wave = np.concatenate([wave1 * env1, wave2 * env2])

    elif style == "exit":
        duration = 0.3
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        f_start, f_end = 600, 300
        phase = 2 * np.pi * (f_start * t + (f_end - f_start) * t**2 / (2 * duration))
        envelope = np.concatenate([
            np.linspace(0, 1, int(fs * 0.05)),
            np.ones(int(fs * 0.15)),
            np.linspace(1, 0, int(fs * 0.1)),
        ])
        wave = 0.5 * np.sin(phase) * envelope

    else:
        return

    try:
        sd.play(wave, samplerate=fs)
        sd.wait()
    except Exception as e:
        print(f"[Audio] Warning: could not play sound: {e}")
