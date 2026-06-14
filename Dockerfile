FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    xdotool \
    libportaudio2 \
    portaudio19-dev \
    libpulse0 \
    pulseaudio-utils \
    wget \
    tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps openwakeword \
    && python -c "import openwakeword; openwakeword.utils.download_models()"

COPY src/ src/
COPY dictate.py .

RUN mkdir -p src/models && \
    python -c "import openwakeword, shutil; \
        paths = openwakeword.get_pretrained_model_paths(); \
        m = next((p for p in paths if 'hey_jarvis' in p), None); \
        shutil.copy(m, 'src/models/hey_jarvis_v0.1.onnx') if m else print('warn: no jarvis model')" && \
    python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"

ENTRYPOINT ["python", "-u", "dictate.py"]
CMD []
