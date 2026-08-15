# 🎙️ VoiceTyper

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Apple Silicon MLX](https://img.shields.io/badge/Apple%20Silicon-Metal%20MLX-000000.svg?logo=apple&logoColor=white)](https://github.com/ml-explore/mlx)
[![Windows 10/11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6.svg?logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**VoiceTyper** is an ultra-low-latency, client-server push-to-talk voice typing system. 

It lets you hold a hotkey (default: `Pause`), speak into your microphone, release the key, and instantly have your speech transcribed and pasted into **any active input field** across Windows (Notion, Telegram, VS Code, Word, web browser, etc.) using hardware-accelerated OpenAI Whisper inference running on an Apple Silicon (Mac mini / MacBook M1/M2/M3/M4) local server.

---

## ✨ Features

- **⚡ Ultra-Low End-to-End Latency (<200ms):**
  - **Apple MLX Metal GPU Engine:** Model inference runs directly on Apple Silicon unified memory.
  - **Server Warm-Up:** Pre-warms model weights in VRAM and compiles Metal computational shaders on daemon startup (**0ms cold start**).
  - **Raw PCM Streaming:** Sends raw `float32 PCM` audio directly in the HTTP body via `/transcribe_raw` without WAV container encoding/decoding overhead.
  - **HTTP Keep-Alive Connection Pool:** Eliminates per-request TCP three-way handshakes.
  - **Continuous Audio Capture:** Eliminates device re-initialization and PortAudio driver overhead.
  - **Atomic Win32 Paste:** Instantly emulates `Ctrl+V` using Win32 API without artificial delays.
- **🎯 Custom Vocabulary Biasing (`initial_prompt`):** Guide Whisper to accurately transcribe specific names, homophones, dialects, and technical terminology.
- **🖥️ Silent Windows Background Mode & System Tray:** Discreet tray icon showing real-time status (Ready, Recording, Processing, Offline) with autostart toggle.
- **🍎 macOS LaunchAgent Daemon:** Runs as an automatic background service on macOS with auto-restart on reboot.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────┐       Local LAN (HTTP Keep-Alive)       ┌────────────────────────────────────────┐
│             Windows Client             │ ──────────────────────────────────────► │        Apple Silicon Mac Server        │
│                                        │                                         │                                        │
│  [Hold Hotkey (e.g. Pause)]            │                                         │  FastAPI + Apple MLX Metal GPU Engine  │
│  1. Continuous Audio Stream (16kHz)    │ ──── Raw Float32 PCM (/transcribe_raw) ►│  1. Pre-Warmed large-v3-turbo Model    │
│  2. Instant Stop on Key Release        │                                         │  2. Greedy Decoding (beam_size=1)      │
│  3. Atomic Ctrl+V via Win32 API        │ ◄─── JSON Response ("transcribed text") ┤  3. Vocabulary Biasing (initial_prompt)│
└────────────────────────────────────────┘                                         └────────────────────────────────────────┘
```

---

## 🚀 Quick Start Guide

### 1. Server Setup (Apple Silicon Mac)

1. Clone repository and install server dependencies:
   ```bash
   git clone https://github.com/petr-timofeev/VoiceTyper.git
   cd VoiceTyper
   pip3 install -r requirements-server.txt
   ```

2. Start the transcription server:
   ```bash
   python3 server_mac.py
   ```

3. *(Optional but Recommended)* Run as a persistent macOS background daemon:
   Create `~/Library/LaunchAgents/com.whisper.server.plist`:
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
           <string>/path/to/VoiceTyper/server_mac.py</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/Users/your_username/whisper_server.log</string>
       <key>StandardErrorPath</key>
       <string>/Users/your_username/whisper_server.log</string>
       <key>WorkingDirectory</key>
       <string>/path/to/VoiceTyper</string>
   </dict>
   </plist>
   ```
   Load and start the daemon:
   ```bash
   launchctl load -w ~/Library/LaunchAgents/com.whisper.server.plist
   ```

---

### 2. Client Setup (Windows)

1. Install client dependencies:
   ```cmd
   pip install -r requirements-client.txt
   ```

2. Configure connection settings:
   Copy `config.example.json` to `config.json` (or let the app auto-generate it):
   ```json
   {
     "server_ip": "192.168.1.100",
     "server_port": 9090,
     "hotkey": "pause",
     "model": "large-v3-turbo",
     "language": "ru",
     "initial_prompt": "Optional terminology, names, or dialect hints.",
     "paste_method": "clipboard",
     "device_keyword": "",
     "sample_rate": 16000
   }
   ```

3. Generate background launcher and shortcuts:
   ```cmd
   python setup_shortcuts.py
   ```
   This creates:
   - `Voice Typer.lnk` on your **Desktop**.
   - `Voice Typer.lnk` in **Windows Startup** folder (starts automatically on login).
   - `VoiceTyper.vbs` for silent background execution without a console window.

4. Start VoiceTyper:
   - Double-click `Voice Typer` on your Desktop or run `python main.py`.

---

## ⚙️ Configuration Reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `server_ip` | string | `"192.168.1.100"` | IP address of your Mac mini / Whisper server on local network. |
| `server_port` | integer | `9090` | Port of the Whisper HTTP server. |
| `hotkey` | string | `"pause"` | Push-to-talk key (`"pause"`, `"insert"`, `"home"`, `"f8"`, etc.). |
| `model` | string | `"large-v3-turbo"` | Whisper model (`"large-v3-turbo"`, `"small"`, `"medium"`, `"large-v3"`). |
| `language` | string | `"ru"` | Language code (`"ru"`, `"en"`, `"de"`, `"fr"`, `"es"`, etc.). |
| `initial_prompt` | string | `""` | Custom vocabulary hint for Whisper to bias recognition toward rare words/names. |
| `paste_method` | string | `"clipboard"` | Text insertion mode (`"clipboard"` for instant Ctrl+V or `"type"` for character typing). |
| `device_keyword` | string | `""` | Substring to match specific microphone name (empty string uses system default). |
| `sample_rate` | integer | `16000` | Audio sampling rate (Whisper requires 16000 Hz). |

---

## 🎯 Usage

1. Verify that the server is running and the tray icon is **green** (`Ready`).
2. Place your cursor inside any text field in any Windows application.
3. **Press and hold the `Pause` key** (the tray icon turns **red** / `Recording`).
4. Speak your text.
5. **Release the `Pause` key** — the transcribed text is automatically pasted at your cursor position within milliseconds!

---

## 🛠️ Troubleshooting & FAQ

<details>
<summary><b>1. Server is offline / Tray icon remains gray</b></summary>

- Check that port `9090` is open and reachable over your local network:
  ```cmd
  curl http://<SERVER_IP>:9090/
  ```
- Make sure macOS Firewall allows incoming connections on port 9090 (System Settings -> Network -> Firewall).
</details>

<details>
<summary><b>2. Text is inserted in the wrong place</b></summary>

- Avoid using navigational keys like `Home` or `End` as hotkeys, as Windows will natively move the caret before recording ends. We recommend `Pause` (Pause/Break) or `Insert`.
</details>

<details>
<summary><b>3. Text is not pasting into Administrator/Elevated windows</b></summary>

- If you are trying to voice-type into an elevated application (e.g., Administrator PowerShell or Task Manager), launch `VoiceTyper` with Administrator privileges so Windows allows global keystroke simulation.
</details>

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
