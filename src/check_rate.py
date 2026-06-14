"""Check supported sample rates for an audio device."""
import sys

import sounddevice as sd

device_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

info = sd.query_devices(device_index)
print(f"Device {device_index}: {info['name']}")
print(f"Default rate: {info['default_samplerate']}Hz")
print()

for rate in (8000, 16000, 32000, 44100, 48000):
    try:
        sd.check_input_settings(device=device_index, channels=1, samplerate=rate)
        print(f"  {rate}Hz: OK")
    except Exception as e:
        print(f"  {rate}Hz: FAILED ({e})")
