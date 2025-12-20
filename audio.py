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

    print(f"Opening stream: Device {device_index}, Rate {native_rate}Hz")
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

