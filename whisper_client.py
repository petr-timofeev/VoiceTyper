import io
import json
import os
import re
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
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

LANGUAGE_MAP = {
    "словенский": "Slovenian",
    "словенски": "Slovenian",
    "словенском": "Slovenian",
    "словенскому": "Slovenian",
    "словенская": "Slovenian",
    "словенскую": "Slovenian",
    "словению": "Slovenian",
    "английский": "English",
    "английском": "English",
    "английскому": "English",
    "инглиш": "English",
    "немецкий": "German",
    "немецком": "German",
    "испанский": "Spanish",
    "испанском": "Spanish",
    "итальянский": "Italian",
    "итальянском": "Italian",
    "французский": "French",
    "французском": "French",
    "сербский": "Serbian",
    "сербском": "Serbian",
    "хорватский": "Croatian",
    "хорватском": "Croatian",
    "русский": "Russian",
    "русском": "Russian",
    "португальский": "Portuguese",
    "турецкий": "Turkish",
    "китайский": "Chinese",
    "японский": "Japanese",
    "slovenian": "Slovenian",
    "slovene": "Slovenian",
    "english": "English",
    "german": "German",
    "spanish": "Spanish",
    "french": "French",
    "italian": "Italian",
    "russian": "Russian",
    "chinese": "Chinese",
    "japanese": "Japanese"
}

TRANSLATE_PATTERN = re.compile(
    r'^(?:переведи|перевод|перевести|translate)\s+(?:на|to|into|по-)?\s*(?P<lang>[а-яa-z\-]+)(?:\s+(?:язык|language))?(?:[:,\-—\s.]+)(?P<payload>.+)$',
    re.IGNORECASE | re.DOTALL
)


def apply_custom_replacements(text: str, replacements: Optional[Dict[str, str]] = None) -> str:
    """Applies custom regex/word replacements to text (e.g. Slavic -> Slovenian)."""
    if not text or not replacements:
        return text

    result = text
    for pattern, repl in replacements.items():
        try:
            result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
        except Exception as e:
            print(f"[REPLACEMENT ERROR] Failed '{pattern}' -> '{repl}': {e}")
    return result


def clean_transcribed_text(text: str) -> str:
    """Cleans transcribed text from hallucinations, brackets, and Whisper repetition loops."""
    if not text:
        return ""
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Check for exact repeated halves (e.g., "Sentence A. Sentence A.")
    words = text.split()
    n = len(words)
    if n >= 4 and n % 2 == 0:
        half = n // 2
        if words[:half] == words[half:]:
            text = " ".join(words[:half])

    # Deduplicate repeated sentences
    parts = re.split(r'(?<=[.!?])\s+', text)
    if len(parts) >= 2:
        deduped = []
        for p in parts:
            p_clean = p.strip().rstrip('.!?')
            if not deduped or p_clean.lower() != deduped[-1].strip().rstrip('.!?').lower():
                deduped.append(p.strip())
        text = " ".join(deduped).strip()

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


def get_gemini_api_key(configured_key: Optional[str] = None) -> Optional[str]:
    """Retrieves Google Gemini API key from parameter, .env file, or environment."""
    if configured_key and configured_key.strip():
        return configured_key.strip()

    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(base_dir, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return None


def translate_via_gemini(
    text: str,
    target_language: str,
    api_key: Optional[str] = None,
    model: str = "gemini-3.5-flash-lite"
) -> str:
    """Translates text ultra-fast (<0.7s) via Google Gemini API."""
    key = get_gemini_api_key(api_key)
    if not key:
        print("[GEMINI TRANSLATE] Warning: No API key found. Falling back to local translation.")
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    system_instruction = (
        f"You are a professional, accurate translator. Translate the given text directly into natural, fluent {target_language}. "
        "Strictly preserve proper capitalization, all punctuation marks (commas, periods, question marks), acronyms, and numbers. "
        "Output ONLY the final translated text without any explanation, markdown, or quotation marks."
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512
        }
    }
    try:
        t0 = time.time()
        resp = _SESSION.post(url, json=payload, timeout=12.0)
        calc_t = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    translated = parts[0].get("text", "").strip()
                    print(f"  [GEMINI TRANSLATION ({target_language})]: {calc_t:.2f}s -> \"{translated}\"")
                    return translated
        else:
            print(f"[GEMINI TRANSLATE ERROR {resp.status_code}]: {resp.text[:200]}")
    except Exception as e:
        print(f"[GEMINI TRANSLATE ERROR]: {e}")
    return ""


def translate_via_http(
    text: str,
    target_language: str,
    server_ip: str = "192.168.1.100",
    server_port: int = 9090
) -> str:
    """Requests local translation from Mac mini server (Ollama Qwen2.5)."""
    try:
        url = f"http://{server_ip}:{server_port}/translate"
        resp = _SESSION.post(
            url,
            json={"text": text, "target_language": target_language},
            timeout=25.0
        )
        if resp.status_code == 200:
            data = resp.json()
            translated = data.get("translated_text", "").strip()
            calc_t = data.get("calc_time_sec", 0.0)
            print(f"  [LOCAL TRANSLATION ({target_language})]: {calc_t:.2f}s -> \"{translated}\"")
            if translated:
                return translated
    except Exception as e:
        print(f"[TRANSLATE HTTP ERROR]: {e}")
    return text


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
            timeout=15.0
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

        resp = _SESSION.post(url, files=files, params=params, timeout=18.0)
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
    initial_prompt: Optional[str] = None,
    custom_replacements: Optional[Dict[str, str]] = None,
    translation_enabled: bool = True,
    translation_engine: str = "gemini",
    gemini_model: str = "gemini-3.5-flash-lite",
    gemini_api_key: Optional[str] = None
) -> str:
    """Main transcription & translation pipeline entrypoint."""
    if audio_data is None or len(audio_data) < 3200:  # < 0.2s
        return ""

    dur_sec = len(audio_data) / 16000.0
    print(f"\n[WHISPER] Sending {dur_sec:.2f}s audio to Whisper server...")

    # 1. Transcribe audio
    raw_text = transcribe_via_http_raw(
        audio_data=audio_data,
        server_ip=server_ip,
        server_port=server_port,
        language=language,
        model=model,
        initial_prompt=initial_prompt
    )

    if raw_text is None:
        print("  [WHISPER] Fallback to WAV multipart...")
        raw_text = transcribe_via_http_wav(
            audio_data=audio_data,
            server_ip=server_ip,
            server_port=server_port,
            language=language,
            model=model,
            initial_prompt=initial_prompt
        )

    if not raw_text:
        return ""

    # 2. Apply guaranteed custom word/regex replacements
    processed_text = apply_custom_replacements(raw_text, custom_replacements)

    # 3. Check for voice translation command ("Переведи на [язык]: ...")
    if translation_enabled:
        match = TRANSLATE_PATTERN.match(processed_text)
        if match:
            raw_lang = match.group("lang").lower()
            payload = match.group("payload").strip()
            target_language = LANGUAGE_MAP.get(raw_lang, raw_lang.capitalize())
            print(f"[TRANSLATION COMMAND] Target: {target_language}, Text: \"{payload}\"")

            # 1. Try Gemini Cloud Translation if configured
            if (translation_engine or "gemini").lower() == "gemini":
                translated = translate_via_gemini(
                    text=payload,
                    target_language=target_language,
                    api_key=gemini_api_key,
                    model=gemini_model
                )
                if translated:
                    return translated
                print("  [WHISPER] Gemini translation unavailable, falling back to local Mac server...")

            # 2. Fallback to local Mac Ollama
            translated = translate_via_http(
                text=payload,
                target_language=target_language,
                server_ip=server_ip,
                server_port=server_port
            )
            return translated

    return processed_text
