import ctypes
import threading
import time
import keyboard
import pyperclip


def send_ctrl_v() -> None:
    """Emulates Ctrl+V keystroke reliably and quickly."""
    try:
        keyboard.send("ctrl+v")
    except Exception:
        VK_CONTROL = 0x11
        VK_V = 0x56
        KEYEVENTF_KEYUP = 0x0002

        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.005)
        ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def paste_via_clipboard(text: str) -> None:
    """Inserts text by temporarily modifying clipboard and triggering instant Ctrl+V."""
    if not text:
        return

    text_to_insert = text.strip() + " "

    # Save previous clipboard content
    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        pyperclip.copy(text_to_insert)
        time.sleep(0.01)  # 10ms clipboard sync buffer
        send_ctrl_v()
    except Exception as e:
        print(f"[INSERTER] Error during clipboard paste: {e}")
        try:
            keyboard.write(text_to_insert)
        except Exception:
            pass

    # Restore previous clipboard in background
    def _restore_clipboard():
        time.sleep(0.6)
        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass

    threading.Thread(target=_restore_clipboard, daemon=True).start()


def paste_via_typing(text: str) -> None:
    """Inserts text character-by-character via keyboard.write."""
    if not text:
        return
    text_to_insert = text.strip() + " "
    try:
        keyboard.write(text_to_insert)
    except Exception as e:
        print(f"[INSERTER] Error during keyboard typing: {e}")


def insert_text(text: str, method: str = "clipboard") -> None:
    """Inserts transcribed text at active cursor position."""
    if not text or not text.strip():
        return

    now_str = time.strftime("%H:%M:%S")
    print(f"[{now_str}] [TRANSCRIBED]: {text.strip()}")

    if method == "type":
        paste_via_typing(text)
    else:
        paste_via_clipboard(text)
