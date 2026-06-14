"""List available audio input devices."""
import sounddevice as sd

print(f"{'ID':<5} {'Name':<45} {'Channels':<10}")
print("-" * 60)
for i, dev in enumerate(sd.query_devices()):
    if dev["max_input_channels"] > 0:
        print(f"{i:<5} {dev['name']:<45} {dev['max_input_channels']:<10}")
