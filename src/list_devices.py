import sounddevice as sd

print(f"{'Index':<5} {'Name':<40} {'Channels':<10}")
print("-" * 60)
for i, dev in enumerate(sd.query_devices()):
    name = dev['name']
    # Filter out likely irrelevant devices
    if dev['max_input_channels'] > 0:
        # crude heuristics to hide monitors/virtuals if desired, 
        # but for now let's just show inputs.
        # The user likely sees "sysdefault", "samplerate", "pulse", etc.
        # We can try to prioritize "USB", "HDA", "Webcam"
        is_physical = any(k in name for k in ['USB', 'HDA', 'Webcam', 'Mic', 'Input'])
        # Also include 'default' and 'pulse' as they are often useful as the system default abstract
        is_system = name in ['default', 'pulse', 'pipewire']
        
        if is_physical or is_system:
             print(f"{i:<5} {name:<40} {dev['max_input_channels']:<10}")
