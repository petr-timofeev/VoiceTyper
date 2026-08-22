import os
import sys
import threading
from typing import Callable, Optional
import winreg
from PIL import Image, ImageDraw
import pystray

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "VoiceTyper"


def is_autostart_enabled() -> bool:
    """Checks whether autostart is enabled in Windows registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_REG_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enable: bool) -> bool:
    """Toggles application autostart in Windows registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                vbs_path = os.path.join(base_dir, "VoiceTyper.vbs")
                if os.path.exists(vbs_path):
                    cmd = f'wscript.exe "{vbs_path}"'
                else:
                    script_path = os.path.join(base_dir, "main.py")
                    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                    cmd = f'"{python_exe}" "{script_path}"'
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
            return True
    except Exception as e:
        print(f"[TRAY] Error toggling autostart: {e}")
        return False


def create_state_icon(color_name: str = "green", size: int = 64) -> Image.Image:
    """Generates a clean status circle icon for system tray."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)

    colors = {
        "green": (46, 204, 113, 255),      # Ready
        "red": (231, 76, 60, 255),        # Recording (Key held)
        "yellow": (241, 196, 15, 255),    # Processing
        "gray": (149, 165, 166, 255)      # Offline / Error
    }
    fill_color = colors.get(color_name, colors["green"])
    margin = 4

    dc.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=fill_color,
        outline=(255, 255, 255, 220),
        width=3
    )
    return image


class TrayApp:
    def __init__(
        self,
        server_ip: str,
        server_port: int,
        hotkey_name: str = "F8",
        asr_engine: str = "gemini",
        translation_engine: str = "gemini",
        on_change_asr_callback: Optional[Callable[[str], None]] = None,
        on_change_translation_callback: Optional[Callable[[str], None]] = None,
        on_exit_callback: Optional[Callable[[], None]] = None
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.hotkey_name = hotkey_name.upper()
        self.asr_engine = (asr_engine or "gemini").lower()
        self.translation_engine = (translation_engine or "gemini").lower()
        self.on_change_asr_callback = on_change_asr_callback
        self.on_change_translation_callback = on_change_translation_callback
        self.on_exit_callback = on_exit_callback
        self.current_state = "ready"

        self.icons = {
            "ready": create_state_icon("green"),
            "recording": create_state_icon("red"),
            "processing": create_state_icon("yellow"),
            "offline": create_state_icon("gray")
        }

        self.icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()

    def _get_tooltip(self, state: str) -> str:
        mode_label = "Gemini Cloud" if self.asr_engine == "gemini" else ("Local Mac" if self.asr_engine == "local" else "Auto")
        tooltips = {
            "ready": f"Voice Typer [{mode_label}]: Ready (Hold {self.hotkey_name})",
            "recording": "Voice Typer: Recording audio...",
            "processing": "Voice Typer: Transcribing & inserting text...",
            "offline": f"Voice Typer: Server {self.server_ip}:{self.server_port} offline"
        }
        return tooltips.get(state, "Voice Typer")

    def _build_menu(self) -> pystray.Menu:
        def on_toggle_autostart(icon, item):
            new_state = not is_autostart_enabled()
            set_autostart(new_state)
            icon.update_menu()

        def set_asr(mode: str):
            def _handler(icon, item):
                self.asr_engine = mode
                if self.on_change_asr_callback:
                    self.on_change_asr_callback(mode)
                self.set_state(self.current_state)
                icon.update_menu()
            return _handler

        def is_asr(mode: str):
            return lambda item: self.asr_engine == mode

        def set_trans(mode: str):
            def _handler(icon, item):
                self.translation_engine = mode
                if self.on_change_translation_callback:
                    self.on_change_translation_callback(mode)
                icon.update_menu()
            return _handler

        def is_trans(mode: str):
            return lambda item: self.translation_engine == mode

        def on_exit(icon, item):
            if self.on_exit_callback:
                self.on_exit_callback()
            icon.stop()

        return pystray.Menu(
            pystray.MenuItem(f"Voice Typer [Key: {self.hotkey_name}]", None, enabled=False),
            pystray.MenuItem(f"Local Server: {self.server_ip}:{self.server_port}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Speech Recognition (ASR)", pystray.Menu(
                pystray.MenuItem("Google Gemini (Cloud)", set_asr("gemini"), checked=is_asr("gemini"), radio=True),
                pystray.MenuItem("Local Whisper (Mac mini)", set_asr("local"), checked=is_asr("local"), radio=True),
                pystray.MenuItem("Auto (Gemini + Local Fallback)", set_asr("auto"), checked=is_asr("auto"), radio=True),
            )),
            pystray.MenuItem("Translator Engine", pystray.Menu(
                pystray.MenuItem("Google Gemini Live (Cloud, 0.6s)", set_trans("gemini"), checked=is_trans("gemini"), radio=True),
                pystray.MenuItem("Local Ollama (Mac mini)", set_trans("local"), checked=is_trans("local"), radio=True),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start with Windows",
                on_toggle_autostart,
                checked=lambda item: is_autostart_enabled()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit)
        )

    def set_state(self, state: str) -> None:
        """Updates tray icon color and tooltip."""
        with self._lock:
            if state not in self.icons:
                state = "ready"
            self.current_state = state

            if self.icon:
                try:
                    self.icon.icon = self.icons[state]
                    self.icon.title = self._get_tooltip(state)
                except Exception:
                    pass

    def _setup_tray(self, icon: pystray.Icon):
        """Called once tray icon loop starts in Windows desktop."""
        icon.visible = True
        self.set_state(self.current_state)

    def run(self) -> None:
        """Runs the system tray icon loop."""
        initial_state = self.current_state if self.current_state in self.icons else "ready"
        self.icon = pystray.Icon(
            name="VoiceTyper",
            icon=self.icons[initial_state],
            title=self._get_tooltip(initial_state),
            menu=self._build_menu()
        )
        self.icon.run(setup=self._setup_tray)

    def stop(self) -> None:
        """Stops tray icon."""
        if self.icon:
            self.icon.stop()
