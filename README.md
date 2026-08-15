# 🎙️ VoiceTyper

**VoiceTyper** — это клиент-серверная система голосового ввода в реальном времени с ультранизкой задержкой (Ultra-Low Latency Voice Typing). 

Система работает по принципу **Push-to-Talk (Hold-to-Talk)**: вы зажимаете горячую клавишу (по умолчанию `Pause`), диктуете текст, отпускаете клавишу — и распознанный текст мгновенно вставляется в активное поле ввода любого приложения Windows (Telegram, Notion, VS Code, Word, браузер и т.д.).

---

## ⚡ Архитектура и Производительность

```
[ Windows Client ]                          [ Mac mini M1 (Metal GPU) ]
 (Hold "Pause" Key)                               (MLX Whisper Engine)
         │                                                 │
 🎙️ Continuous PCM Stream ───────────────────────────► 🚀 Warm Model (large-v3-turbo)
    (Float32 16kHz)       Raw HTTP/1.1 Keep-Alive          │ 0ms Cold Start / Greedy Decoding
         │                                                 │
 ⌨️ Atomic Win32 Paste ◄────────────────────────────── 💬 Transcribed Text
    (SendInput / Ctrl+V)      JSON Response (<150ms)
```

- **Инференс на Apple Silicon Metal GPU (MLX Whisper):** Модель `whisper-large-v3-turbo` оптимизирована под унифицированную память Apple Silicon.
- **Предварительный прогрев (Warm-up):** При старте сервера веса модели загружаются в Metal VRAM, а шейдеры компилируются заранее — **0 мс задержки на холодный старт**.
- **Сырой бинарный поток (Raw PCM Streaming):** Аудио отправляется через эндпоинт `/transcribe_raw` в виде `float32 PCM` напрямую в теле запроса без накладных расходов на упаковку в WAV контейнеры.
- **Постоянный пул соединений (HTTP Keep-Alive):** Никаких повторных TCP 3-way handshakes между клиентом и сервером.
- **Мгновенная вставка (Atomic Win32 SendInput):** Текст помещается в системный буфер обмена и мгновенно эмулируется `Ctrl+V`.
- **Поддержка `initial_prompt`:** Тонкая настройка словарного запаса Whisper для идеального распознавания специфических терминов, географических названий и словарных форм (например, контекст Словении, словенского языка и т.д.).
- **Интеграция с Windows Tray:** Иконка в трее со статусами готовности, записи, обработки и переключателем автозапуска.

---

## 📁 Структура Проекта

| Файл | Назначение |
|---|---|
| `main.py` | Главная точка входа клиента Windows, управление треем и горячими клавишами |
| `server_mac.py` | Высокопроизводительный сервер Whisper на базе FastAPI и Apple MLX Metal GPU |
| `audio_recorder.py` | Непрерывный аудиозахват без задержек и перезапусков звукового потока |
| `whisper_client.py` | Сетевой клиент с пулом HTTP Keep-Alive и бинарной передачей данных |
| `text_inserter.py` | Модуль атомарной быстрой вставки текста через буфер обмена и Win32 API |
| `tray_app.py` | Системный трей Windows (статусы, меню, автозагрузка через реестр) |
| `config.py` / `config.json` | Конфигурация клиента (сервер, хоткей, модель, язык, initial_prompt) |
| `VoiceTyper.vbs` / `VoiceTyper.bat` | Лаунчеры для бесшумного фонового запуска без окна консоли |
| `create_shortcuts.py` | Создание ярлыков на Рабочем столе и в автозагрузке Windows |

---

## 🚀 Установка и Настройка

### 1. Серверная часть (Mac mini / Apple Silicon)

1. Установите зависимости:
```bash
pip3 install mlx-whisper fastapi uvicorn soundfile numpy
```

2. Запустите сервер:
```bash
python3 server_mac.py
```

*(Опционально)* Для автоматического запуска демона в macOS создайте `~/Library/LaunchAgents/com.whisper.server.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whisper.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/your_user/server_mac.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/your_user/whisper_server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/your_user/whisper_server.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/your_user</string>
</dict>
</plist>
```
И загрузите службу:
```bash
launchctl load -w ~/Library/LaunchAgents/com.whisper.server.plist
```

---

### 2. Клиентская часть (Windows)

1. Установите зависимости Python:
```cmd
pip install -r requirements.txt
```

2. Настройте `config.json`:
```json
{
  "server_ip": "192.168.64.150",
  "server_port": 9090,
  "hotkey": "pause",
  "model": "large-v3-turbo",
  "language": "ru",
  "initial_prompt": "Словения, Любляна, словенский язык, словенский, словенская, словенские, словенского, словенскому, словенском, словенцы, по-словенски.",
  "paste_method": "clipboard",
  "device_keyword": "H2n",
  "sample_rate": 16000
}
```

3. Запустите клиент:
- **Для отладки:** `python main.py`
- **В тихом фоновом режиме:** двойной клик по `VoiceTyper.vbs` (или `VoiceTyper.bat`)

---

## 🎯 Использование

1. Убедитесь, что сервер на Mac mini запущен и иконка VoiceTyper в трее Windows зеленая (`Готов`).
2. Поставьте текстовый курсор в любое поле ввода (в браузере, коде, мессенджере).
3. **Зажмите клавишу `Pause`** (или другую настроенную клавишу) — иконка станет красной (`Запись`).
4. Наговорите фразу.
5. **Отпустите клавишу** — текст моментально вставится в позицию курсора!

---

## 📄 Лицензия
MIT License
