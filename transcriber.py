import numpy as np
import time
from faster_whisper import WhisperModel
from audio import audio_queue
import webrtcvad
import queue

# Global state
model = None
vad = webrtcvad.Vad(2) # Mode 2 is aggressive
BUFFER_SECONDS = 30
audio_buffer = np.zeros(0, dtype=np.float32)
last_text = ""

def load_model(model_size="base.en"):
    global model
    print(f"Loading Whisper model: {model_size} ...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("Model loaded.")

def is_speech(chunk):
    # webrtcvad expects 16-bit PCM, 16000Hz
    pcm = (chunk * 32768).astype(np.int16).tobytes()
    return vad.is_speech(pcm, 16000)

def transcribe_loop():
    global audio_buffer, last_text
    
    # Import here to avoid circular init issues if any, though not expected
    from audio import fetch_audio, audio_queue

    # Create a generator instance
    stream = fetch_audio()

    while True:
        # blocking get for the first chunk
        try:
             # We use the generator manually
             chunk = next(stream)
        except StopIteration:
             break

        new_data = [chunk.flatten()]
        
        # Non-blocking drain
        # We need to be careful: fetch_audio blocks on queue.get()
        # So we can't just call it in a loop without checking queue size.
        # But fetch_audio encapsulates the queue.
        # We should check audio_queue.empty() directly before asking fetch_audio for more?
        # Yes, audio.audio_queue is global.
        
        while not audio_queue.empty():
            # Consume all pending audio
            # next(stream) will do the queue.get() and resample
            new_data.append(next(stream).flatten())
                
        audio_buffer = np.concatenate([audio_buffer, *new_data])

        # Wait until we have enough audio for VAD/Whisper
        if len(audio_buffer) < 16000:
            continue
            
        # Transcribe with word timestamps to help segmentation? Faster-whisper gives segments by default.
        segments_gen, _ = model.transcribe(
            audio_buffer,
            language="en",
            vad_filter=True,
            beam_size=1
        )
        
        # Manifest the generator to a list so we can inspect indices
        segments = list(segments_gen)
        
        if not segments:
            continue

        # Logic: 
        # If we have > 1 segment, we treat the first N-1 segments as FINAL.
        # The last segment is PARTIAL (unless it seems very long or stable?)
        # We assume the last segment is still being spoken or refined.
        
        final_text = ""
        partial_text = ""
        
        if len(segments) > 1:
            # We have at least one finalized segment
            # Take all except the last one
            final_segments = segments[:-1]
            partial_chunk = segments[-1]
            
            final_text = " ".join(s.text.strip() for s in final_segments)
            partial_text = partial_chunk.text.strip()
            
            # Trim audio buffer!
            # We need to cut up to the end of the last finalized segment.
            cut_time = final_segments[-1].end
            cut_samples = int(cut_time * 16000)
            
            # Safety: Ensure we don't cut more than we have (though impossible if timestamps are correct)
            if cut_samples < len(audio_buffer):
                audio_buffer = audio_buffer[cut_samples:]
            else:
                audio_buffer = np.zeros(0, dtype=np.float32)
                
            # Yield final text first
            if final_text:
                yield (final_text, True)
                
        else:
            # Only 1 segment, assume it's all partial for now
            partial_text = segments[0].text.strip()
            # Optimization: If the buffer is huge (>15s) and still only 1 segment, 
            # maybe force commit? But let's trust Whisper for now.

        # Yield partial text
        if partial_text != last_text:
            yield (partial_text, False)
            last_text = partial_text
        elif not partial_text:
            # If we cleared everything to final, partial might be empty, need to signal that?
            # Actually dictate.py just needs to know current partial state. 
            # If partial became empty (because it moved to final), we should yield empty partial 
            # so dictate can clear its committed buffer.
            yield ("", False)
            last_text = ""
