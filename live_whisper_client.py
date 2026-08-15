import json
import re
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np
import websocket


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


class LiveWhisperClient:
    """Клиент реального времени: передает звук на Mac mini во время удержания клавиши."""

    def __init__(
        self,
        server_ip: str = "192.168.64.150",
        server_port: int = 9090,
        model: str = "medium",
        language: str = "ru"
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.model = model
        self.language = language

        self.ws_app: Optional[websocket.WebSocketApp] = None
        self.is_connected = False
        self.is_ready = False
        self.ready_event = threading.Event()

        self.latest_segments: List[Dict[str, Any]] = []
        self.fallback_texts: List[str] = []
        self.lock = threading.Lock()
        self.session_active = False

        self._stop_bg = False
        self._thread: Optional[threading.Thread] = None

    def start_connection_thread(self):
        """Запускает фоновое поддержание соединения с сервером."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_bg = False
        self._thread = threading.Thread(target=self._connection_worker, daemon=True)
        self._thread.start()

    def _connection_worker(self):
        """Фоновый цикл автоподключения и переподключения к серверу."""
        while not self._stop_bg:
            if not self.is_connected:
                self._connect_once()
            time.sleep(2.0)

    def _connect_once(self):
        if not is_server_available(self.server_ip, self.server_port):
            self.is_connected = False
            self.is_ready = False
            return

        self.ready_event.clear()
        url = f"ws://{self.server_ip}:{self.server_port}"

        def on_open(ws):
            self.is_connected = True
            config = {
                "uid": f"live_{int(time.time() * 1000)}",
                "language": self.language,
                "task": "transcribe",
                "model": self.model,
                "use_vad": False
            }
            try:
                ws.send(json.dumps(config))
            except Exception:
                pass

        def on_message(ws, message):
            try:
                d = json.loads(message)
                if d.get("message") == "SERVER_READY":
                    self.is_ready = True
                    self.ready_event.set()

                if "segments" in d and isinstance(d["segments"], list) and d["segments"]:
                    with self.lock:
                        self.latest_segments.clear()
                        self.latest_segments.extend(d["segments"])
                    texts = [s.get("text", "").strip() for s in d["segments"] if s.get("text")]
                    cur_end = d["segments"][-1].get("end", "0.0")
                    if self.session_active:
                        print(f"  [ЖИВОЙ ПОТОК ({cur_end}с)]: {' '.join(texts)}")
                elif "text" in d and d["text"]:
                    with self.lock:
                        txt = d["text"].strip()
                        if txt and txt not in self.fallback_texts:
                            self.fallback_texts.append(txt)
            except Exception:
                pass

        def on_close(ws, close_code, close_msg):
            self.is_connected = False
            self.is_ready = False
            self.ready_event.clear()

        def on_error(ws, error):
            self.is_connected = False
            self.is_ready = False

        self.ws_app = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        self.ws_app.run_forever()

    def wait_ready(self, timeout: float = 15.0) -> bool:
        """Ожидает подтверждения готовности модели на сервере."""
        if self.is_ready:
            return True
        return self.ready_event.wait(timeout=timeout)

    def start_session(self):
        """Начинает новую сессию записи при нажатии клавиши."""
        with self.lock:
            self.latest_segments.clear()
            self.fallback_texts.clear()
            self.session_active = True

    def send_audio_chunk(self, chunk_f32: np.ndarray):
        """Отправляет кусочек звука (100мс) на Mac mini в реальном времени."""
        if not self.is_connected or not self.ws_app or not self.ws_app.sock or not self.ws_app.sock.connected:
            return
        try:
            raw_bytes = chunk_f32.tobytes()
            self.ws_app.send(raw_bytes, opcode=websocket.ABNF.OPCODE_BINARY)
        except Exception:
            pass

    def finish_session(self, total_dur: float, post_flush_sec: float = 1.5) -> str:
        """Завершает сессию при отпускании клавиши: шлёт сброс (flush) и забирает текст."""
        self.session_active = False

        # Отправляем тишину (flush) для финализации окна распознавания
        chunk_samples = 1600
        flush = np.zeros(int(16000 * post_flush_sec), dtype=np.float32)
        for i in range(0, len(flush), chunk_samples):
            self.send_audio_chunk(flush[i:i+chunk_samples])
            time.sleep(0.005)

        # Ожидаем завершения сегмента (для Live Streaming задержка минимальна: 0.5 - 2.0 сек)
        t_start = time.time()
        max_wait = min(6.0, max(2.0, total_dur * 0.35 + 1.0))

        while time.time() - t_start < max_wait:
            with self.lock:
                if self.latest_segments:
                    try:
                        last_end = float(self.latest_segments[-1].get("end", 0.0) or 0.0)
                        if last_end >= (total_dur - 1.2):
                            time.sleep(0.3)
                            break
                    except Exception:
                        pass
            time.sleep(0.1)

        with self.lock:
            if self.latest_segments:
                raw_text = " ".join([s.get("text", "").strip() for s in self.latest_segments if s.get("text")])
            else:
                raw_text = " ".join(self.fallback_texts).strip()

        return clean_transcribed_text(raw_text)

    def close(self):
        """Закрывает соединение."""
        self._stop_bg = True
        if self.ws_app:
            try:
                self.ws_app.close()
            except Exception:
                pass
