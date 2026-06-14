from __future__ import annotations

import logging
import os

import numpy as np

logging.getLogger("openwakeword").setLevel(logging.ERROR)
from openwakeword.model import Model

SAMPLE_RATE = 16000
DETECTION_THRESHOLD = 0.6


class WakeWordListener:
    def __init__(self, models: list[str] | None = None):
        if models is None:
            model_path = os.path.join(
                os.path.dirname(__file__), "models", "hey_jarvis_v0.1.onnx"
            )
            models = [model_path]

        print(f"[Wake] Loading models: {models}")
        self.model = Model(wakeword_models=models)

    def process_chunk(self, chunk: np.ndarray) -> str | None:
        """
        Process a float32 16kHz audio chunk.
        Returns detected wake word name or None.
        """
        chunk = np.clip(chunk, -1.0, 1.0).flatten()
        data = (chunk * 32768).astype(np.int16)

        self.model.predict(data)

        for mdl_name in self.model.prediction_buffer:
            score = self.model.prediction_buffer[mdl_name][-1]
            if score > DETECTION_THRESHOLD:
                self.model.reset()
                return mdl_name

        return None

    def reset(self) -> None:
        self.model.reset()
