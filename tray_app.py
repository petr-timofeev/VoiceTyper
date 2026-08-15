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
        hotkey_name: str = "PAUSE",
        on_exit_callback: Optional[Callable[[], None]] = None
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.hotkey_name = hotkey_name.upper()
        self.on_exit_callback = on_exit_callback
        self.current_state = "gray"

        self.icons = {
            "ready": create_state_icon("green"),
            "recording": create_state_icon("red"),
            "processing": create_state_icon("yellow"),
            "offline": create_state_icon("gray")
        }

        self.icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()

    def _build_menu(self) -> pystray.Menu:
        def on_toggle_autostart(icon, item):
            new_state = not is_autostart_enabled()
            set_autostart(new_state)
            icon.update_menu()

        def on_exit(icon, item):
            if self.on_exit_callback:
                self.on_exit_callback()
            icon.stop()

        return pystray.Menu(
            pystray.MenuItem(f"Voice Typer [Key: {self.hotkey_name}]", None, enabled=False),
            pystray.MenuItem(f"Server: {self.server_ip}:{self.server_port}", None, enabled=False),
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

            tooltips = {
                "ready": f"Voice Typer: Ready (Hold {self.hotkey_name})",
                "recording": "Voice Typer: Recording audio...",
                "processing": "Voice Typer: Transcribing & inserting text...",
                "offline": f"Voice Typer: Server {self.server_ip}:{self.server_port} offline"
            }

            if self.icon:
                self.icon.icon = self.icons[state]
                self.icon.title = tooltips.get(state, "Voice Typer")

    def run(self) -> None:
        """Runs the system tray icon loop."""
        self.icon = pystray.Icon(
            name="VoiceTyper",
            icon=self.icons["offline"],
            title="Voice Typer: Starting...",
            menu=self._build_menu()
        )
        self.icon.run()

    def stop(self) -> None:
        """Stops tray icon."""
        if self.icon:
            self.icon.stop()
