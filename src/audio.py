import sounddevice as sd
import numpy as np
import queue
from scipy import signal

TARGET_RATE = 16000
BLOCK_DURATION = 0.2  # 200ms

audio_queue = queue.Queue()
current_native_rate = 16000 # Default/Fallback

def start_stream(device_index=None):
    global current_native_rate
    
    # Query device native rate
    # Query device native rate
    if device_index is not None:
        # Resolve string name to index if needed
        if isinstance(device_index, str):
            found_index = None
            try:
                # Try to parse as int first (legacy support)
                found_index = int(device_index)
                device_index = found_index
            except ValueError:
                # Search by name
                devices = sd.query_devices()
                target = device_index
                # Exact match first
                for i, dev in enumerate(devices):
                    if dev['name'] == target and dev['max_input_channels'] > 0:
                        found_index = i
                        break
                # Partial match second
                if found_index is None:
                    for i, dev in enumerate(devices):
                        if target in dev['name'] and dev['max_input_channels'] > 0:
                            found_index = i
                            break
                
                if found_index is not None:
                    print(f"Resolved device '{device_index}' to index {found_index} ({devices[found_index]['name']})")
                    device_index = found_index
                else:
                    raise ValueError(f"Could not find input device matching: {device_index}")

        info = sd.query_devices(device_index, 'input')
        native_rate = info['default_samplerate']
    else:
        defaults = sd.query_devices(kind='input')
        native_rate = defaults['default_samplerate']

    # Round native rate
    native_rate = int(native_rate)
    current_native_rate = native_rate
    
    block_size = int(native_rate * BLOCK_DURATION)

    def audio_callback(indata, frames, time, status):
        if status:
            print(status)
        # Fast path: just copy to queue
        audio_queue.put(indata.copy())

    print(f"OpeningStream: Device {device_index}, Rate {native_rate}Hz")
    # Clear old data
    with audio_queue.mutex:
        audio_queue.queue.clear()
        
    return sd.InputStream(
        device=device_index,
        samplerate=native_rate,
        channels=1,
        blocksize=block_size,
        callback=audio_callback,
        dtype=np.float32
    )

def fetch_audio():
    """Generator that yields resampled 16kHz float32 chunks from the queue."""
    global current_native_rate
    
    while True:
        # Blocking get
        raw_chunk = audio_queue.get()
        
        # Resample if necessary
        if current_native_rate != TARGET_RATE:
            num_samples = int(len(raw_chunk) * TARGET_RATE / current_native_rate)
            # This is heavy, but now it runs in the main thread (transcriber loop), not the audio thread
            yield signal.resample(raw_chunk, num_samples).astype(np.float32)
        else:
            yield raw_chunk


def play_sound(style="wake", device_index=None):
    """
    Generates and plays synthetic sounds.
    styles: 'wake', 'success', 'exit'
    """
    fs = 44100
    
    if style == "wake":
        duration = 0.2
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        envelope = np.concatenate([np.linspace(0, 1, int(fs*0.05)), np.ones(int(fs*0.1)), np.linspace(1, 0, int(fs*0.05))])
        wave = 0.5 * np.sin(2 * np.pi * 880.0 * t) * envelope # A5
        
    elif style == "success":
        # Two ascending tones (Ding-Ding)
        duration = 0.3
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        # Split into two notes
        len_note = len(t) // 2
        t1 = t[:len_note]
        t2 = t[len_note:]
        
        wave1 = 0.5 * np.sin(2 * np.pi * 880.0 * t1) 
        wave2 = 0.5 * np.sin(2 * np.pi * 1108.0 * t2) # C#6
        
        # Apply envelopes
        env1 = np.concatenate([np.linspace(0, 1, int(fs*0.02)), np.linspace(1, 0, len_note - int(fs*0.02))])
        env2 = np.concatenate([np.linspace(0, 1, int(fs*0.02)), np.linspace(1, 0, len(t2) - int(fs*0.02))])
        
        wave = np.concatenate([wave1 * env1, wave2 * env2])
        
    elif style == "exit":
        # Descending tone
        duration = 0.3
        t = np.linspace(0, duration, int(fs * duration), endpoint=False)
        # Chirp down
        f_start = 600
        f_end = 300
        phase = 2 * np.pi * (f_start * t + (f_end - f_start) * t**2 / (2 * duration))
        envelope = np.concatenate([np.linspace(0, 1, int(fs*0.05)), np.ones(int(fs*0.15)), np.linspace(1, 0, int(fs*0.1))])
        wave = 0.5 * np.sin(phase) * envelope
        
    else:
        return

    try:
        sd.play(wave, samplerate=fs, device=device_index)
        sd.wait()
    except Exception as e:
        print(f"Warning: Could not play sound: {e}")

# Backward compat
play_chime = lambda device_index=None: play_sound("wake", device_index)

