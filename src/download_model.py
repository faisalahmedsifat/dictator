import argparse
from faster_whisper import WhisperModel

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="base.en", help="Model to download")
    args = parser.parse_args()

    print(f"Downloading Whisper model '{args.model}' int8...")
    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8"
    )
    print("Model downloaded successfully.")
