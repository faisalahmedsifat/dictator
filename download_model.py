from faster_whisper import WhisperModel

print("Downloading Whisper model 'medium' int8...")
model = WhisperModel(
    "medium",
    device="cpu",
    compute_type="int8"
)
print("Model downloaded successfully.")
