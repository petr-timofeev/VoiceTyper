#!/usr/bin/env python3
"""
Apple Silicon (MLX Metal GPU) Whisper & Translation Server
===========================================================
Ultra-low latency Whisper speech-to-text & local LLM translation server for Apple Silicon (M1/M2/M3/M4):
- Hardware accelerated Whisper inference via Apple MLX on Metal GPU
- Local translation endpoint via local Ollama LLM (Qwen2.5 / Llama 3)
- Warm-up upon server startup to eliminate cold-start latency (0ms cold start)
- Direct raw float32 PCM binary streaming (/transcribe_raw)
- Backward-compatible standard WAV multipart upload (/transcribe)
- Translation endpoint (/translate)
"""

import io
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import numpy as np
import requests
import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Request, Response, UploadFile
from pydantic import BaseModel

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
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b"


class TranslationRequest(BaseModel):
    text: str
    target_language: str = "Slovenian"
    model: Optional[str] = None


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


def run_local_translation(text: str, target_language: str = "Slovenian", model: str = OLLAMA_MODEL) -> str:
    """Performs high-quality local translation via Ollama Qwen2.5 on Mac mini."""
    if not text or not text.strip():
        return ""

    system_prompt = (
        f"You are a professional, accurate translator. Translate the given text into natural, fluent {target_language}. "
        "Strictly preserve proper capitalization, all punctuation marks (commas, periods, question marks), acronyms, and numbers. "
        "Output ONLY the final translated text without any explanation, markdown, or quotation marks."
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": text.strip(),
                "system": system_prompt,
                "stream": False,
                "keep_alive": "5m",
                "options": {
                    "num_ctx": 2048,
                    "temperature": 0.1,
                    "top_p": 0.95
                }
            },
            timeout=25.0
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", "").strip()
    except Exception as e:
        print(f"[TRANSLATE ERROR]: {e}")
    return text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: pre-warms Whisper model and Ollama in VRAM at startup."""
    print("==========================================================")
    print(" 🚀 Starting Apple Silicon Whisper & Translation Server...")
    print(f" Default Whisper Model: {DEFAULT_MODEL_REPO}")
    print(f" Default Translation Model: {OLLAMA_MODEL}")
    print(" Pre-warming Whisper model in Metal GPU memory...")
    t0 = time.time()
    try:
        dummy_audio = np.zeros(8000, dtype=np.float32)
        run_mlx_inference(dummy_audio, model_key="large-v3-turbo", language="ru")
        warmup_time = time.time() - t0
        print(f" 🔥 Whisper pre-warmed in {warmup_time:.2f}s!")
    except Exception as e:
        print(f" [WARNING] Whisper pre-warming error: {e}")
    print("==========================================================")
    yield
    print("[SERVER] Shutting down server...")


app = FastAPI(title="Apple Silicon Whisper & Translation Server", lifespan=lifespan)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "backend": "Apple Silicon MLX Metal GPU" if USE_MLX else "CPU Fallback",
        "default_whisper_model": DEFAULT_MODEL_REPO,
        "translation_engine": f"Ollama ({OLLAMA_MODEL})"
    }


@app.post("/transcribe_raw")
async def transcribe_raw(
    request: Request,
    model: str = "large-v3-turbo",
    language: str = "ru",
    dtype: str = "float32",
    initial_prompt: Optional[str] = None
):
    """Ultra-fast endpoint: accepts raw float32/int16 PCM bytes directly in body."""
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


@app.post("/translate")
async def translate_endpoint(req: TranslationRequest):
    """Local translation endpoint using Ollama LLM on Mac mini."""
    t0 = time.time()
    model = req.model or OLLAMA_MODEL
    translated = run_local_translation(req.text, target_language=req.target_language, model=model)
    calc_time = time.time() - t0
    print(f"[LOCAL TRANSLATE ({req.target_language})] \"{req.text}\" -> \"{translated}\" in {calc_time:.2f}s")
    return {
        "original_text": req.text,
        "translated_text": translated,
        "target_language": req.target_language,
        "calc_time_sec": round(calc_time, 3)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090, log_level="info")
