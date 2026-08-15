import ctypes
import threading
import time
import keyboard
import pyperclip


def send_ctrl_v() -> None:
    """Надёжно и быстро эмулирует нажатие Ctrl+V."""
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
    """Вставляет текст через подмену буфера обмена и моментальный Ctrl+V."""
    if not text:
        return

    text_to_insert = text.strip() + " "

    # Сохраняем предыдущий буфер
    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        # Копируем текст в буфер
        pyperclip.copy(text_to_insert)
        time.sleep(0.01)  # 10мс синхронизация буфера с Windows

        # Эмуляция вставки
        send_ctrl_v()
    except Exception as e:
        print(f"[INSERTER] Ошибка вставки через буфер: {e}")
        try:
            keyboard.write(text_to_insert)
        except Exception:
            pass

    # Восстанавливаем буфер обмена в фоне
    def _restore_clipboard():
        time.sleep(0.6)
        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass

    threading.Thread(target=_restore_clipboard, daemon=True).start()


def paste_via_typing(text: str) -> None:
    """Вставляет текст посимвольно через keyboard.write."""
    if not text:
        return
    text_to_insert = text.strip() + " "
    try:
        keyboard.write(text_to_insert)
    except Exception as e:
        print(f"[INSERTER] Ошибка посимвольного ввода: {e}")


def insert_text(text: str, method: str = "clipboard") -> None:
    """Вставляет распознанный текст в позицию активного курсора."""
    if not text or not text.strip():
        return

    now_str = time.strftime("%H:%M:%S")
    print(f"[{now_str}] [РАСПОЗНАНО]: {text.strip()}")

    if method == "type":
        paste_via_typing(text)
    else:
        paste_via_clipboard(text)
