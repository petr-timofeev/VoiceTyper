import os
import threading
import time
from typing import Callable, List, Optional
import wave
import numpy as np
import sounddevice as sd

LAST_RECORDING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_recording.wav")


def find_microphone_device(keyword: str = "H2n") -> Optional[int]:
    """Ищет микрофон по ключевому слову в названии, исключая WDM-KS драйверы."""
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        for i, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                hostapi_id = dev.get("hostapi", 0)
                api_name = hostapis[hostapi_id].get("name", "") if hostapi_id < len(hostapis) else ""
                dev_name = dev.get("name", "")
                if "WDM-KS" not in api_name:
                    if keyword.lower() in dev_name.lower() or "zoom" in dev_name.lower() or "микрофон" in dev_name.lower():
                        return i
    except Exception as e:
        print(f"[AUDIO] Ошибка поиска микрофона: {e}")
    return None


def normalize_audio(audio_data: np.ndarray, target_peak: float = 0.90) -> np.ndarray:
    """Автоматически нормализует громкость звука до оптимального уровня для Whisper (пик 0.9)."""
    if audio_data is None or len(audio_data) == 0:
        return audio_data

    max_val = float(np.max(np.abs(audio_data)))
    if max_val > 1e-4:
        gain = min(target_peak / max_val, 25.0)
        return np.clip(audio_data * gain, -1.0, 1.0)
    return audio_data


def save_audio_to_wav_async(audio_data: np.ndarray, file_path: str = LAST_RECORDING_PATH, sample_rate: int = 16000) -> None:
    """Сохраняет WAV файл асинхронно в фоне без задержек основного пайплайна."""
    def _worker():
        try:
            int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(file_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(int16_data.tobytes())
        except Exception as e:
            print(f"[AUDIO] Ошибка сохранения WAV: {e}")

    threading.Thread(target=_worker, daemon=True).start()


class AudioRecorder:
    """Высокопроизводительный модуль непрерывного аудиозахвата с нулевой задержкой."""

    def __init__(self, sample_rate: int = 16000, device_keyword: str = "H2n", live_gain: float = 4.0):
        self.sample_rate = sample_rate
        self.device_keyword = device_keyword
        self.live_gain = live_gain
        self.device_id = find_microphone_device(device_keyword)
        self.stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._frames: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._chunk_callback: Optional[Callable[[np.ndarray], None]] = None

        # Запускаем постоянный поток захвата
        self._init_stream()

    def _init_stream(self):
        """Инициализирует и запускает непрерывный аудиопоток."""
        def _sd_callback(indata, frames, time_info, status):
            if self._is_recording:
                # Применяем live gain (аппаратная компенсация)
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
                blocksize=800,  # 50мс чанки для быстрого отклика
                callback=_sd_callback
            )
            self.stream.start()
        except Exception as e:
            print(f"[AUDIO] Ошибка инициализации InputStream: {e}")
            self.stream = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self, chunk_callback: Optional[Callable[[np.ndarray], None]] = None) -> bool:
        """Мгновенно активирует накопление аудиосемплов (0 мс задержка)."""
        with self._lock:
            self._frames.clear()
            self._chunk_callback = chunk_callback
            self._is_recording = True

        # Если поток упал — восстанавливаем
        if self.stream is None or not self.stream.active:
            self._init_stream()
        return True

    def stop(self, post_roll_sec: float = 0.0) -> Optional[np.ndarray]:
        """Мгновенно останавливает запись и возвращает нормализованный float32 массив."""
        with self._lock:
            if not self._is_recording:
                return None
            self._is_recording = False

            if not self._frames:
                return None

            raw_audio = np.concatenate(self._frames)
            self._frames.clear()

        # Нормализация
        normalized_audio = normalize_audio(raw_audio, target_peak=0.90)

        # Фоновое сохранение WAV для отладки (без блокировки отклика)
        save_audio_to_wav_async(normalized_audio, LAST_RECORDING_PATH, self.sample_rate)
        return normalized_audio

    def close(self):
        """Закрывает аудиопоток при выходе из программы."""
        with self._lock:
            self._is_recording = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
