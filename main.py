import ctypes
import os
import sys
import threading
import time

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_typer.log")

# Safe stdout/stderr redirection for pythonw.exe (no console crash)
if sys.stdout is None:
    try:
        sys.stdout = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    except Exception:
        pass
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if sys.stderr is None:
    try:
        sys.stderr = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    except Exception:
        pass
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
from pynput import keyboard as pynput_keyboard

from audio_recorder import AudioRecorder, LAST_RECORDING_PATH
from config import load_config
from text_inserter import insert_text
from tray_app import TrayApp
from whisper_client import is_server_available, transcribe_batch


class VoiceTyperApp:
    def __init__(self):
        self.config = load_config()
        self.server_ip = self.config.get("server_ip", "192.168.1.100")
        self.server_port = int(self.config.get("server_port", 9090))
        self.hotkey_name = self.config.get("hotkey", "pause").lower()
        self.model = self.config.get("model", "large-v3-turbo")
        self.language = self.config.get("language", "ru")
        self.initial_prompt = self.config.get("initial_prompt", "")
        self.custom_replacements = self.config.get("custom_replacements", {})
        self.translation_enabled = bool(self.config.get("translation_enabled", True))
        self.paste_method = self.config.get("paste_method", "clipboard")
        self.sample_rate = int(self.config.get("sample_rate", 16000))
        self.device_keyword = self.config.get("device_keyword", "")

        self.audio = AudioRecorder(
            sample_rate=self.sample_rate,
            device_keyword=self.device_keyword,
            live_gain=1.0
        )

        self.tray = TrayApp(
            server_ip=self.server_ip,
            server_port=self.server_port,
            hotkey_name=self.hotkey_name,
            on_exit_callback=self.shutdown
        )

        self.is_key_down = False
        self.is_processing = False
        self.is_running = True
        self._lock = threading.Lock()

    def is_target_key(self, key) -> bool:
        """Checks if pressed key matches configured push-to-talk hotkey."""
        target = self.hotkey_name.lower()

        if target in ("pause", "pause_break"):
            if key == pynput_keyboard.Key.pause:
                return True
            if getattr(key, "name", "") in ("pause", "pause_break"):
                return True
            if getattr(key, "vk", 0) == 19:  # VK_PAUSE
                return True
        elif target == "f8":
            if key == pynput_keyboard.Key.f8 or getattr(key, "name", "") == "f8" or getattr(key, "vk", 0) == 119:
                return True
        elif target == "f9":
            if key == pynput_keyboard.Key.f9 or getattr(key, "name", "") == "f9" or getattr(key, "vk", 0) == 120:
                return True
        elif target == "f10":
            if key == pynput_keyboard.Key.f10 or getattr(key, "name", "") == "f10" or getattr(key, "vk", 0) == 121:
                return True
        elif target in ("scroll_lock", "scrolllock"):
            if key == pynput_keyboard.Key.scroll_lock or getattr(key, "name", "") in ("scroll_lock", "scrolllock") or getattr(key, "vk", 0) == 145:
                return True
        elif target == "home":
            if key == pynput_keyboard.Key.home:
                return True
            if getattr(key, "name", "") == "home":
                return True
            if getattr(key, "vk", 0) == 36:  # VK_HOME
                return True
        elif target == "insert":
            if key == pynput_keyboard.Key.insert:
                return True
            if getattr(key, "name", "") == "insert":
                return True
            if getattr(key, "vk", 0) == 45:  # VK_INSERT
                return True
        else:
            if getattr(key, "name", "") == target or str(key).strip("'") == target:
                return True
        return False

    def on_key_press(self, key):
        if not self.is_target_key(key):
            return

        with self._lock:
            if self.is_key_down or self.is_processing:
                return
            self.is_key_down = True

        print(f"\n[{time.strftime('%H:%M:%S')}] >>> [{self.hotkey_name.upper()} PRESSED]: Recording audio...")
        self.tray.set_state("recording")
        self.audio.start()

    def on_key_release(self, key):
        if not self.is_target_key(key):
            return

        with self._lock:
            if not self.is_key_down:
                return
            self.is_key_down = False
            self.is_processing = True

        print(f"[{time.strftime('%H:%M:%S')}] <<< [{self.hotkey_name.upper()} RELEASED]: Transcribing audio...")
        self.tray.set_state("processing")
        audio_data = self.audio.stop(post_roll_sec=0.0)

        if audio_data is None or len(audio_data) < 3200:
            print("[INFO] Audio too short (< 0.2s). Skipping.")
            self.tray.set_state("ready")
            with self._lock:
                self.is_processing = False
            return

        dur = len(audio_data) / self.sample_rate
        print(f"[AUDIO] Captured {dur:.2f}s audio. Sending to Whisper server...")

        def _process_in_background():
            try:
                t0 = time.time()
                text = transcribe_batch(
                    audio_data=audio_data,
                    server_ip=self.server_ip,
                    server_port=self.server_port,
                    language=self.language,
                    model=self.model,
                    initial_prompt=self.initial_prompt,
                    custom_replacements=self.custom_replacements,
                    translation_enabled=self.translation_enabled
                )
                latency = time.time() - t0

                if text:
                    print(f"[SUCCESS ({latency:.2f}s)]: Transcribed: \"{text}\"")
                    insert_text(text, method=self.paste_method)
                else:
                    print(f"[INFO ({latency:.2f}s)]: No speech detected.")
            except Exception as e:
                print(f"[ERROR] Processing error: {e}")
            finally:
                with self._lock:
                    self.is_processing = False
                self.tray.set_state("ready")

        threading.Thread(target=_process_in_background, daemon=True).start()

    def _start_heartbeat(self):
        """Periodically pings Whisper server in background to keep tray icon status accurate."""
        def _worker():
            while self.is_running:
                time.sleep(8.0)
                if not self.is_key_down and not self.is_processing:
                    online = is_server_available(self.server_ip, self.server_port)
                    target_state = "ready" if online else "offline"
                    if self.tray.current_state != target_state:
                        self.tray.set_state(target_state)
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def shutdown(self):
        """Cleans up audio capture and background workers."""
        print("[VOICE TYPER] Shutting down...")
        self.is_running = False
        self.audio.stop(post_roll_sec=0.0)
        self.audio.close()

    def start(self):
        print("==================================================")
        print(" VoiceTyper Windows Client Started!")
        print(f" Whisper Server: http://{self.server_ip}:{self.server_port}")
        print(f" Model: {self.model}")
        print(f" Push-to-Talk Key: [{self.hotkey_name.upper()}] (Hold while speaking)")
        print(f" Log File: {LOG_PATH}")
        print(" System Tray Icon is active.")
        print("==================================================")

        # Initial server check
        if is_server_available(self.server_ip, self.server_port):
            self.tray.set_state("ready")
        else:
            print("[WARNING] Whisper server is currently offline or unreachable.")
            self.tray.set_state("offline")

        # Start periodic background health check
        self._start_heartbeat()

        keyboard_listener = pynput_keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        keyboard_listener.daemon = True
        keyboard_listener.start()

        try:
            self.tray.run()
        except KeyboardInterrupt:
            self.shutdown()


def acquire_single_instance_lock(mutex_name: str = "VoiceTyper_SingleInstance_Mutex"):
    """Ensures only a single instance of VoiceTyper runs on Windows."""
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    if not mutex or last_error == ERROR_ALREADY_EXISTS:
        return None
    return mutex


if __name__ == "__main__":
    mutex = acquire_single_instance_lock()
    if not mutex:
        print("[VOICE TYPER] Another instance of VoiceTyper is already running. Exiting.")
        sys.exit(0)

    app = VoiceTyperApp()
    try:
        app.start()
    finally:
        if mutex:
            try:
                ctypes.windll.kernel32.CloseHandle(mutex)
            except Exception:
                pass
