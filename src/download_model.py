"""Pre-download and cache a Whisper model."""
import argparse

from faster_whisper import WhisperModel

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download a Whisper model")
    parser.add_argument("--model", type=str, default="base.en")
    args = parser.parse_args()

    print(f"Downloading Whisper model '{args.model}'...")
    WhisperModel(args.model, device="cpu", compute_type="int8")
    print("Done.")
