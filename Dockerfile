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
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps openwakeword

COPY src/ src/
COPY dictate.py .

RUN mkdir -p src/models

ARG DOWNLOAD_MODELS=true
RUN if [ "$DOWNLOAD_MODELS" = "true" ]; then \
    echo "Downloading Qwen model..." && \
    wget -q --show-progress -O src/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf" && \
    python -c "import openwakeword, shutil; \
        paths = openwakeword.get_pretrained_model_paths(); \
        m = next((p for p in paths if 'hey_jarvis' in p), None); \
        shutil.copy(m, 'src/models/hey_jarvis_v0.1.onnx') if m else print('warn: no jarvis model')" && \
    python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"; \
    fi

ENTRYPOINT ["python", "-u", "dictate.py"]
CMD []
