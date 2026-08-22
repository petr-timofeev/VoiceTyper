import ctypes
import threading
import time
from ctypes import wintypes
from typing import Optional
import pyperclip

user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_V = 0x56


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT)
    ]


def type_via_unicode(text: str) -> None:
    """Injects Unicode text directly into active window using Win32 SendInput.
    
    Completely bypasses the clipboard - zero clipboard footprint or interference!
    """
    if not text:
        return

    text_to_type = text.strip() + " "
    utf16_units = text_to_type.encode("utf-16-le")
    events = []

    for i in range(0, len(utf16_units), 2):
        code_point = int.from_bytes(utf16_units[i:i+2], byteorder="little")

        # Key down
        inp_down = INPUT()
        inp_down.type = INPUT_KEYBOARD
        inp_down.ki = KEYBDINPUT(
            wVk=0,
            wScan=code_point,
            dwFlags=KEYEVENTF_UNICODE,
            time=0,
            dwExtraInfo=0
        )
        events.append(inp_down)

        # Key up
        inp_up = INPUT()
        inp_up.type = INPUT_KEYBOARD
        inp_up.ki = KEYBDINPUT(
            wVk=0,
            wScan=code_point,
            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=0
        )
        events.append(inp_up)

    if events:
        n = len(events)
        arr = (INPUT * n)(*events)
        user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def send_ctrl_v() -> None:
    """Simulates a clean, atomic Ctrl+V keystroke without moving the cursor."""
    user32.keybd_event(VK_CONTROL, 0x1D, 0, 0)
    user32.keybd_event(VK_V, 0x2F, 0, 0)
    time.sleep(0.015)
    user32.keybd_event(VK_V, 0x2F, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0x1D, KEYEVENTF_KEYUP, 0)


def paste_via_clipboard(text: str, restore_clipboard: bool = True) -> None:
    """Inserts text via clipboard and automatically restores previous clipboard content.
    
    Preserves whatever the user had in the clipboard (code, text, links, etc.).
    """
    if not text:
        return

    text_to_insert = text.strip() + " "

    # 1. Backup original clipboard content
    old_clipboard: Optional[str] = None
    if restore_clipboard:
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = None

    # 2. Copy and paste transcribed text
    try:
        pyperclip.copy(text_to_insert)
        time.sleep(0.025)  # 25ms buffer for clipboard sync
        send_ctrl_v()
    except Exception as e:
        print(f"[INSERTER] Error during clipboard paste: {e}")

    # 3. Restore original clipboard content in background after active app handles Ctrl+V
    if restore_clipboard and old_clipboard is not None:
        def _restore_worker(saved_content: str):
            time.sleep(0.12)  # 120ms grace period for target app to consume Ctrl+V
            try:
                pyperclip.copy(saved_content)
            except Exception:
                pass

        threading.Thread(target=_restore_worker, args=(old_clipboard,), daemon=True).start()


def insert_text(text: str, method: str = "clipboard", restore_clipboard: bool = True) -> None:
    """Inserts transcribed text at cursor position using configured method."""
    if not text or not text.strip():
        return

    now_str = time.strftime("%H:%M:%S")
    print(f"[{now_str}] [TRANSCRIBED]: {text.strip()}")

    if method.lower() in ("type", "sendinput", "unicode"):
        type_via_unicode(text)
    else:
        paste_via_clipboard(text, restore_clipboard=restore_clipboard)
