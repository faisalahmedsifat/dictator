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
    if device_index is not None:
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

