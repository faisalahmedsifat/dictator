import sounddevice as sd
import sys

device_index = 4
if len(sys.argv) > 1:
    device_index = int(sys.argv[1])

print(f"Testing device {device_index}...")

rates = [8000, 16000, 32000, 44100, 48000]
supported = []

for r in rates:
    try:
        sd.check_input_settings(device=device_index, channels=1, samplerate=r)
        print(f"  {r}Hz: OK")
        supported.append(r)
    except Exception as e:
        print(f"  {r}Hz: FAILED ({e})")

print(f"Supported rates: {supported}")

try:
    info = sd.query_devices(device_index)
    print(f"Default Sample Rate: {info['default_samplerate']}")
except Exception as e:
    print(f"Could not query info: {e}")
