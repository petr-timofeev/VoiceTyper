import ctypes
import threading
import time
from ctypes import wintypes
from typing import Dict, Optional
import pyperclip

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
user32.EnumClipboardFormats.restype = wintypes.UINT
user32.GetClipboardSequenceNumber.argtypes = []
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD

GMEM_MOVEABLE = 0x0002
# Synthesized / GDI handle formats that Windows manages automatically
SYNTHESIZED_OR_HANDLE_FORMATS = {1, 2, 3, 7, 9, 14}

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


def open_clipboard_with_retry(hwnd: int = 0, retries: int = 5, delay: float = 0.01) -> bool:
    """Tries to open Windows clipboard with small backoff in case another app holds it."""
    for _ in range(retries):
        if user32.OpenClipboard(hwnd):
            return True
        time.sleep(delay)
    return False


def backup_clipboard() -> Dict[int, bytes]:
    """Captures all raw clipboard formats (including screenshots, images, DIB, files, HTML, text)."""
    data_dict = {}
    if not open_clipboard_with_retry():
        return data_dict
    try:
        fmt = 0
        while True:
            fmt = user32.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            if fmt in SYNTHESIZED_OR_HANDLE_FORMATS:
                continue
            hData = user32.GetClipboardData(fmt)
            if not hData:
                continue
            sz = kernel32.GlobalSize(hData)
            if sz == 0:
                continue
            pData = kernel32.GlobalLock(hData)
            if not pData:
                continue
            try:
                raw_bytes = (ctypes.c_char * sz).from_address(pData).raw
                data_dict[fmt] = raw_bytes
            finally:
                kernel32.GlobalUnlock(hData)
    except Exception as e:
        print(f"[INSERTER] Error backing up clipboard: {e}")
    finally:
        user32.CloseClipboard()
    return data_dict


def restore_clipboard(data_dict: Dict[int, bytes]) -> None:
    """Restores all previously saved clipboard formats accurately without loss."""
    if not open_clipboard_with_retry():
        return
    try:
        user32.EmptyClipboard()
        if data_dict:
            for fmt, raw_bytes in data_dict.items():
                hMem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw_bytes))
                if not hMem:
                    continue
                pMem = kernel32.GlobalLock(hMem)
                if pMem:
                    ctypes.memmove(pMem, raw_bytes, len(raw_bytes))
                    kernel32.GlobalUnlock(hMem)
                    user32.SetClipboardData(fmt, hMem)
    except Exception as e:
        print(f"[INSERTER] Error restoring clipboard: {e}")
    finally:
        user32.CloseClipboard()


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


def paste_via_clipboard(text: str, do_restore: bool = True) -> None:
    """Inserts text via clipboard and automatically restores previous clipboard content.
    
    Preserves whatever the user had in the clipboard (screenshots, images, code, text, files, etc.).
    If the clipboard was empty, it restores it back to empty instead of leaving transcribed text.
    """
    if not text:
        return

    text_to_insert = text.strip() + " "

    # 1. Full binary snapshot of original clipboard content
    saved_clipboard = backup_clipboard() if do_restore else None

    # 2. Copy and paste transcribed text
    expected_seq = 0
    try:
        pyperclip.copy(text_to_insert)
        time.sleep(0.025)  # 25ms buffer for clipboard sync
        expected_seq = user32.GetClipboardSequenceNumber()
        send_ctrl_v()
    except Exception as e:
        print(f"[INSERTER] Error during clipboard paste: {e}")

    # 3. Restore original clipboard content in background after active app consumes Ctrl+V
    if do_restore and saved_clipboard is not None:
        def _restore_worker(data_to_restore: Dict[int, bytes], expected_sequence: int):
            time.sleep(0.12)  # 120ms grace period for target app to consume Ctrl+V
            try:
                # Only restore if user hasn't explicitly copied something new in the meantime
                current_seq = user32.GetClipboardSequenceNumber()
                if current_seq == expected_sequence:
                    restore_clipboard(data_to_restore)
            except Exception as e:
                print(f"[INSERTER] Restore worker error: {e}")

        threading.Thread(target=_restore_worker, args=(saved_clipboard, expected_seq), daemon=True).start()


def insert_text(text: str, method: str = "clipboard", do_restore: bool = True) -> None:
    """Inserts transcribed text at cursor position using configured method."""
    if not text or not text.strip():
        return

    now_str = time.strftime("%H:%M:%S")
    print(f"[{now_str}] [TRANSCRIBED]: {text.strip()}")

    if method.lower() in ("type", "sendinput", "unicode"):
        type_via_unicode(text)
    else:
        paste_via_clipboard(text, do_restore=do_restore)
