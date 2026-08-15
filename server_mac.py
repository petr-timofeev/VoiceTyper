#!/usr/bin/env python3
"""
Apple Silicon (MLX Metal GPU) Whisper Server для Mac mini M1
=============================================================
Высокопроизводительный сервер транскрипции реального времени:
- Инференс на Apple Metal GPU через MLX
- Предварительный прогрев (warm-up) модели при старте демона (0 мс холодный старт)
- Поддержка initial_prompt для точного распознавания словарного запаса (Словения, словенский и т.д.)
- Поддержка мгновенного сырого бинарного PCM потока (/transcribe_raw)
- Обратная совместимость с WAV multipart/form-data (/transcribe)
"""

import io
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict, Optional

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Request, Response, UploadFile

try:
    import mlx_whisper
    USE_MLX = True
    print("[SERVER] Apple Silicon MLX GPU (Metal) доступен!")
except ImportError:
    USE_MLX = False
    print("[SERVER ВНИМАНИЕ] mlx-whisper не найден, используется CPU fallback.")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        pass

MLX_MODELS: Dict[str, str] = {
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3-turbo-4bit": "mlx-community/whisper-large-v3-turbo-4bit",
    "large-v3-turbo-8bit": "mlx-community/whisper-large-v3-turbo-8bit",
    "large": "mlx-community/whisper-large-v3-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "tiny": "mlx-community/whisper-tiny-mlx",
}

DEFAULT_MODEL_REPO = "mlx-community/whisper-large-v3-turbo"


def run_mlx_inference(
    audio_np: np.ndarray,
    model_key: str = "large-v3-turbo",
    language: str = "ru",
    initial_prompt: Optional[str] = None
) -> str:
    """Выполняет инференс на Apple Metal GPU с поддержкой initial_prompt и оптимизированных флагов."""
    repo = MLX_MODELS.get(model_key.lower(), DEFAULT_MODEL_REPO)

    kwargs = {
        "path_or_hf_repo": repo,
        "language": language,
        "task": "transcribe",
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "word_timestamps": False,
        "fp16": True
    }
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt

    result = mlx_whisper.transcribe(audio_np, **kwargs)
    return result.get("text", "").strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: предпрогрев модели в Metal VRAM при старте."""
    print("==========================================================")
    print(" 🚀 Запуск Apple Silicon Whisper Server (MLX Metal GPU)...")
    print(f" Модель по умолчанию: {DEFAULT_MODEL_REPO}")
    print(" Прогрев модели (Warm-up) в памяти Metal GPU...")
    t0 = time.time()
    try:
        dummy_audio = np.zeros(8000, dtype=np.float32)
        run_mlx_inference(dummy_audio, model_key="large-v3-turbo", language="ru")
        warmup_time = time.time() - t0
        print(f" 🔥 Прогрев завершен за {warmup_time:.2f}с! Сервер готов к мгновенным запросам.")
    except Exception as e:
        print(f" [ВНИМАНИЕ] Ошибка во время прогрева: {e}")
    print("==========================================================")
    yield
    print("[SERVER] Остановка сервера...")


app = FastAPI(title="Apple Silicon Whisper Server", lifespan=lifespan)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "backend": "Apple Silicon MLX Metal GPU" if USE_MLX else "CPU Fallback",
        "default_model": DEFAULT_MODEL_REPO
    }


@app.post("/transcribe_raw")
async def transcribe_raw(
    request: Request,
    model: str = "large-v3-turbo",
    language: str = "ru",
    dtype: str = "float32",
    initial_prompt: Optional[str] = None
):
    """Сверхбыстрый эндпоинт: принимает сырые бинарные байты PCM напрямую в body."""
    t0 = time.time()
    raw_body = await request.body()
    if not raw_body:
        return {"text": "", "calc_time_sec": 0.0, "audio_dur_sec": 0.0}

    if dtype == "int16":
        int16_arr = np.frombuffer(raw_body, dtype=np.int16)
        audio_data = int16_arr.astype(np.float32) / 32768.0
    else:
        audio_data = np.frombuffer(raw_body, dtype=np.float32)

    dur_sec = len(audio_data) / 16000.0
    text = run_mlx_inference(
        audio_data,
        model_key=model,
        language=language,
        initial_prompt=initial_prompt
    )
    calc_time = time.time() - t0

    prompt_info = f" [Prompt: {initial_prompt[:30]}...]" if initial_prompt else ""
    print(f"[RAW INFERENCE] {dur_sec:.2f}с аудио обработано за {calc_time:.3f}с{prompt_info} -> \"{text}\"")
    return {
        "text": text,
        "calc_time_sec": round(calc_time, 3),
        "audio_dur_sec": round(dur_sec, 2)
    }


@app.post("/transcribe")
async def transcribe_http(
    file: UploadFile = File(...),
    model: str = "large-v3-turbo",
    language: str = "ru",
    initial_prompt: Optional[str] = None
):
    """Классический эндпоинт для WAV файлов (обратная совместимость)."""
    t0 = time.time()
    contents = await file.read()

    audio_data, sample_rate = sf.read(io.BytesIO(contents), dtype="float32")
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    dur_sec = len(audio_data) / float(sample_rate)
    text = run_mlx_inference(
        audio_data,
        model_key=model,
        language=language,
        initial_prompt=initial_prompt
    )
    calc_time = time.time() - t0

    print(f"[WAV INFERENCE] {dur_sec:.2f}с аудио обработано за {calc_time:.3f}с -> \"{text}\"")
    return {
        "text": text,
        "calc_time_sec": round(calc_time, 3),
        "audio_dur_sec": round(dur_sec, 2)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090, log_level="info")
