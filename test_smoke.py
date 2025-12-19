try:
    print("Importing modules...")
    import audio
    import inject
    import transcriber
    print("Modules imported.")

    print("Checking Whisper model loading...")
    # This should be cached and fast
    from faster_whisper import WhisperModel
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    print("Model loaded successfully.")

    print("Checking Audio (sounddevice)...")
    import sounddevice as sd
    # Query devices just to ensure we can access PortAudio
    sd.query_devices()
    print("Audio devices queried successfully.")

    print("Smoke test PASSED.")
except Exception as e:
    print(f"Smoke test FAILED: {e}")
    exit(1)
