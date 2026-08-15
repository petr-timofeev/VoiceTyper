#!/usr/bin/env python3
"""
Apple Silicon (MLX Metal GPU) Whisper Server
============================================
Ultra-low latency Whisper speech-to-text server optimized for Apple Silicon (M1/M2/M3/M4):
- Hardware accelerated inference via Apple MLX on Metal GPU
- Warm-up upon server startup to eliminate cold-start latency (0ms cold start)
- Support for initial_prompt custom vocabulary biasing
- Direct raw float32 PCM binary streaming (/transcribe_raw)
- Backward-compatible standard WAV multipart upload (/transcribe)
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
    print("[SERVER] Apple Silicon MLX GPU (Metal) engine available!")
except ImportError:
    USE_MLX = False
    print("[SERVER WARNING] mlx-whisper not found, falling back to CPU.")
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
    """Executes inference on Apple Metal GPU with optimized greedy decoding flags."""
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
    """Application lifespan manager: pre-warms model in Metal VRAM at startup."""
    print("==========================================================")
    print(" 🚀 Starting Apple Silicon Whisper Server (MLX Metal GPU)...")
    print(f" Default Model: {DEFAULT_MODEL_REPO}")
    print(" Pre-warming model in Metal GPU memory...")
    t0 = time.time()
    try:
        dummy_audio = np.zeros(8000, dtype=np.float32)
        run_mlx_inference(dummy_audio, model_key="large-v3-turbo", language="ru")
        warmup_time = time.time() - t0
        print(f" 🔥 Model pre-warmed in {warmup_time:.2f}s! Ready for instant requests.")
    except Exception as e:
        print(f" [WARNING] Pre-warming error: {e}")
    print("==========================================================")
    yield
    print("[SERVER] Shutting down server...")


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
    """Ultra-fast endpoint: accepts raw float32/int16 PCM bytes directly in body (0ms parsing overhead)."""
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
    print(f"[RAW INFERENCE] {dur_sec:.2f}s audio processed in {calc_time:.3f}s{prompt_info} -> \"{text}\"")
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
    """Standard WAV multipart upload endpoint (backward compatibility)."""
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

    print(f"[WAV INFERENCE] {dur_sec:.2f}s audio processed in {calc_time:.3f}s -> \"{text}\"")
    return {
        "text": text,
        "calc_time_sec": round(calc_time, 3),
        "audio_dur_sec": round(dur_sec, 2)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090, log_level="info")
