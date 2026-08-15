import os
import threading
import time
from typing import Callable, List, Optional
import wave
import numpy as np
import sounddevice as sd

LAST_RECORDING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_recording.wav")


def find_microphone_device(keyword: str = "") -> Optional[int]:
    """Finds an audio input device matching keyword, avoiding WDM-KS drivers."""
    if not keyword:
        return None  # Use system default input device

    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        for i, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                hostapi_id = dev.get("hostapi", 0)
                api_name = hostapis[hostapi_id].get("name", "") if hostapi_id < len(hostapis) else ""
                dev_name = dev.get("name", "")
                if "WDM-KS" not in api_name:
                    if keyword.lower() in dev_name.lower():
                        return i
    except Exception as e:
        print(f"[AUDIO] Error querying audio devices: {e}")
    return None


def normalize_audio(audio_data: np.ndarray, target_peak: float = 0.90) -> np.ndarray:
    """Normalizes audio volume to optimal level for Whisper inference."""
    if audio_data is None or len(audio_data) == 0:
        return audio_data

    max_val = float(np.max(np.abs(audio_data)))
    if max_val > 1e-4:
        gain = min(target_peak / max_val, 25.0)
        return np.clip(audio_data * gain, -1.0, 1.0)
    return audio_data


def save_audio_to_wav_async(audio_data: np.ndarray, file_path: str = LAST_RECORDING_PATH, sample_rate: int = 16000) -> None:
    """Saves debug WAV recording asynchronously in background thread."""
    def _worker():
        try:
            int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(file_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(int16_data.tobytes())
        except Exception as e:
            print(f"[AUDIO] Error saving WAV: {e}")

    threading.Thread(target=_worker, daemon=True).start()


class AudioRecorder:
    """High-performance continuous audio capture module with zero startup latency."""

    def __init__(self, sample_rate: int = 16000, device_keyword: str = "", live_gain: float = 1.0):
        self.sample_rate = sample_rate
        self.device_keyword = device_keyword
        self.live_gain = live_gain
        self.device_id = find_microphone_device(device_keyword) if device_keyword else None
        self.stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._frames: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._chunk_callback: Optional[Callable[[np.ndarray], None]] = None

        # Keep stream active continuously
        self._init_stream()

    def _init_stream(self):
        """Initializes and starts persistent audio input stream."""
        def _sd_callback(indata, frames, time_info, status):
            if self._is_recording:
                boosted = np.clip(indata.copy() * self.live_gain, -1.0, 1.0)
                with self._lock:
                    if self._is_recording:
                        self._frames.append(boosted)
                if self._chunk_callback:
                    self._chunk_callback(boosted)

        try:
            self.stream = sd.InputStream(
                device=self.device_id,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=800,  # 50ms chunks
                callback=_sd_callback
            )
            self.stream.start()
        except Exception as e:
            print(f"[AUDIO] Error initializing InputStream: {e}")
            self.stream = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self, chunk_callback: Optional[Callable[[np.ndarray], None]] = None) -> bool:
        """Instantly enables audio accumulation (0ms latency)."""
        with self._lock:
            self._frames.clear()
            self._chunk_callback = chunk_callback
            self._is_recording = True

        if self.stream is None or not self.stream.active:
            self._init_stream()
        return True

    def stop(self, post_roll_sec: float = 0.0) -> Optional[np.ndarray]:
        """Stops recording and returns normalized float32 numpy array."""
        with self._lock:
            if not self._is_recording:
                return None
            self._is_recording = False

            if not self._frames:
                return None

            raw_audio = np.concatenate(self._frames)
            self._frames.clear()

        normalized_audio = normalize_audio(raw_audio, target_peak=0.90)
        save_audio_to_wav_async(normalized_audio, LAST_RECORDING_PATH, self.sample_rate)
        return normalized_audio

    def close(self):
        """Closes audio stream cleanly upon exit."""
        with self._lock:
            self._is_recording = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
