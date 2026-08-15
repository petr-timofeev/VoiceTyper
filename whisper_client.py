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
import websocket

# Глобальный пул постоянных HTTP Keep-Alive соединений
_SESSION = requests.Session()
_ADAPTER = requests.adapters.HTTPAdapter(
    pool_connections=5,
    pool_maxsize=10,
    max_retries=1
)
_SESSION.mount("http://", _ADAPTER)
_SESSION.mount("https://", _ADAPTER)


def clean_transcribed_text(text: str) -> str:
    """Очищает распознанный текст от типичных галлюцинаций и артефактов Whisper."""
    if not text:
        return ""
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_server_available(ip: str, port: int, timeout: float = 1.5) -> bool:
    """Проверяет доступность сервера через быстрый TCP сокет."""
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
    server_ip: str = "192.168.64.150",
    server_port: int = 9090,
    language: str = "ru",
    model: str = "large-v3-turbo",
    initial_prompt: Optional[str] = None
) -> Optional[str]:
    """Отправляет сырые float32 байты через постоянное HTTP Keep-Alive соединение."""
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
            print(f"  [MAC MINI GPU (MLX RAW)]: Инференс: {calc_t:.3f}с")
            return clean_transcribed_text(text)
    except Exception as e:
        print(f"[HTTP RAW ОШИБКА]: {e}")
    return None


def transcribe_via_http_wav(
    audio_data: np.ndarray,
    server_ip: str = "192.168.64.150",
    server_port: int = 9090,
    language: str = "ru",
    model: str = "large-v3-turbo",
    initial_prompt: Optional[str] = None
) -> Optional[str]:
    """Fallback эндпоинт: отправляет WAV через multipart/form-data."""
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
            print(f"  [MAC MINI GPU (MLX WAV)]: Инференс: {calc_t:.3f}с")
            return clean_transcribed_text(text)
    except Exception as e:
        print(f"[HTTP WAV ОШИБКА]: {e}")
    return None


def transcribe_batch(
    audio_data: np.ndarray,
    server_ip: str = "192.168.64.150",
    server_port: int = 9090,
    language: str = "ru",
    model: str = "large-v3-turbo",
    initial_prompt: Optional[str] = None
) -> str:
    """Основная точка входа: пробует быстрый /transcribe_raw, затем /transcribe."""
    if audio_data is None or len(audio_data) < 3200:  # < 0.2 сек
        return ""

    dur_sec = len(audio_data) / 16000.0
    print(f"\n[WHISPER] Отправка {dur_sec:.2f} сек. аудио на Mac mini...")

    # 1. Сверхбыстрый raw PCM поток
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

    # 2. Fallback на стандартный WAV POST
    print("  [WHISPER] Fallback на multipart WAV...")
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
