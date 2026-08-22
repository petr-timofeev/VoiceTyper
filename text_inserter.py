import ctypes
import time
import pyperclip

user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def send_ctrl_v() -> None:
    """Simulates a clean, atomic Ctrl+V keystroke without moving the cursor."""
    # Press Ctrl (scan code 0x1D)
    user32.keybd_event(VK_CONTROL, 0x1D, 0, 0)
    # Press V (scan code 0x2F)
    user32.keybd_event(VK_V, 0x2F, 0, 0)
    time.sleep(0.015)
    # Release V
    user32.keybd_event(VK_V, 0x2F, KEYEVENTF_KEYUP, 0)
    # Release Ctrl
    user32.keybd_event(VK_CONTROL, 0x1D, KEYEVENTF_KEYUP, 0)


def paste_via_clipboard(text: str) -> None:
    """Inserts transcribed text via Windows clipboard and Ctrl+V cleanly.
    
    Inserts text at the EXACT cursor position with a trailing space.
    No background threads, no cursor displacement, no modifier leaks.
    """
    if not text:
        return

    text_to_insert = text.strip() + " "

    try:
        pyperclip.copy(text_to_insert)
        time.sleep(0.025)  # 25ms clipboard buffer
        send_ctrl_v()
    except Exception as e:
        print(f"[INSERTER] Error during clipboard paste: {e}")


def insert_text(text: str, method: str = "clipboard") -> None:
    """Inserts transcribed text at cursor position."""
    if not text or not text.strip():
        return

    now_str = time.strftime("%H:%M:%S")
    print(f"[{now_str}] [TRANSCRIBED]: {text.strip()}")

    paste_via_clipboard(text)
