import io
import json
import re
import socket
import threading
import time
from typing import Any, Dict, List, Optional
import numpy as np
import requests
import soundfile as sf

# Global HTTP Keep-Alive connection pool
_SESSION = requests.Session()
_ADAPTER = requests.adapters.HTTPAdapter(
    pool_connections=5,
    pool_maxsize=10,
    max_retries=1
)
_SESSION.mount("http://", _ADAPTER)
_SESSION.mount("https://", _ADAPTER)


def clean_transcribed_text(text: str) -> str:
    """Cleans transcribed text from typical Whisper hallucinations and brackets."""
    if not text:
        return ""
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_server_available(ip: str, port: int, timeout: float = 1.5) -> bool:
    """Checks server availability via fast TCP socket connection."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        res = sock.connect_ex((ip, port))
        sock.close()
        return res == 0
    except Exception:
        return False


def transcribe_via_http_raw(
    audio_data: np.ndarray,
    server_ip: str = "192.168.1.100",
    server_port: int = 9090,
    language: str = "ru",
    model: str = "large-v3-turbo",
    initial_prompt: Optional[str] = None
) -> Optional[str]:
    """Transmits raw float32 PCM bytes via persistent HTTP Keep-Alive connection."""
    try:
        url = f"http://{server_ip}:{server_port}/transcribe_raw"
        raw_bytes = audio_data.astype(np.float32).tobytes()
        params = {"model": model, "language": language, "dtype": "float32"}
        if initial_prompt:
            params["initial_prompt"] = initial_prompt

        resp = _SESSION.post(
            url,
            data=raw_bytes,
            params=params,
            headers={"Content-Type": "application/octet-stream"},
            timeout=10.0
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("text", "").strip()
            calc_t = data.get("calc_time_sec", 0.0)
            print(f"  [GPU INFERENCE]: {calc_t:.3f}s")
            return clean_transcribed_text(text)
    except Exception as e:
        print(f"[HTTP RAW ERROR]: {e}")
    return None


def transcribe_via_http_wav(
    audio_data: np.ndarray,
    server_ip: str = "192.168.1.100",
    server_port: int = 9090,
    language: str = "ru",
    model: str = "large-v3-turbo",
    initial_prompt: Optional[str] = None
) -> Optional[str]:
    """Fallback endpoint: transmits WAV via multipart/form-data."""
    try:
        buf = io.BytesIO()
        sf.write(buf, audio_data, 16000, format="WAV", subtype="PCM_16")
        buf.seek(0)

        url = f"http://{server_ip}:{server_port}/transcribe"
        files = {"file": ("audio.wav", buf, "audio/wav")}
        params = {"model": model, "language": language}
        if initial_prompt:
            params["initial_prompt"] = initial_prompt

        resp = _SESSION.post(url, files=files, params=params, timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("text", "").strip()
            calc_t = data.get("calc_time_sec", 0.0)
            print(f"  [GPU INFERENCE WAV]: {calc_t:.3f}s")
            return clean_transcribed_text(text)
    except Exception as e:
        print(f"[HTTP WAV ERROR]: {e}")
    return None


def transcribe_batch(
    audio_data: np.ndarray,
    server_ip: str = "192.168.1.100",
    server_port: int = 9090,
    language: str = "ru",
    model: str = "large-v3-turbo",
    initial_prompt: Optional[str] = None
) -> str:
    """Main transcription entrypoint: tries raw PCM endpoint first, then WAV fallback."""
    if audio_data is None or len(audio_data) < 3200:  # < 0.2s
        return ""

    dur_sec = len(audio_data) / 16000.0
    print(f"\n[WHISPER] Sending {dur_sec:.2f}s audio to Whisper server...")

    # 1. Ultra-fast raw PCM stream
    res = transcribe_via_http_raw(
        audio_data=audio_data,
        server_ip=server_ip,
        server_port=server_port,
        language=language,
        model=model,
        initial_prompt=initial_prompt
    )
    if res is not None:
        return res

    # 2. Fallback to standard WAV multipart
    print("  [WHISPER] Fallback to WAV multipart...")
    res_wav = transcribe_via_http_wav(
        audio_data=audio_data,
        server_ip=server_ip,
        server_port=server_port,
        language=language,
        model=model,
        initial_prompt=initial_prompt
    )
    if res_wav is not None:
        return res_wav

    return ""
