import numpy as np
from openwakeword.model import Model
import collections

# Parameters
# openWakeWord works best with ~80ms chunks (1280 samples at 16kHz)
# But it can handle flexible sizes.
SAMPLE_RATE = 16000

class WakeWordListener:
    def __init__(self, models=None):
        if models is None:
            import os
            models = [os.path.join(os.path.dirname(__file__), "models", "hey_jarvis_v0.1.onnx")]

        print(f"Loading Wake Word Models: {models} ...")
        self.fd_model = Model(wakeword_model_paths=models)
        self.running = False

    def process_chunk(self, chunk):
        """
        Process a chunk of audio (float32, 16kHz).
        Returns the detected wake word (str) or None.
        """
        # Convert to int16 16khz mono
        # openwakeword expects 16-bit PCM 
        # chunk is float32 [-1, 1]
        
        # Clip to -1.0, 1.0 before casting to avoid wrap-around filtering artifacts?
        chunk = np.clip(chunk, -1.0, 1.0).flatten()
        data = (chunk * 32768).astype(np.int16)
        
        # Feed to model
        # predict() accumulates internal buffer.
        self.fd_model.predict(data)
        
        # Check predictions
        detected_word = None
        for mdl in self.fd_model.prediction_buffer.keys():
            score = self.fd_model.prediction_buffer[mdl][-1]
            if score > 0.6: # Threshold
                detected_word = mdl
                self.fd_model.reset()
                break # Return first detected
        
        return detected_word

    def reset(self):
        self.fd_model.reset()
