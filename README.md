# 🎙️ VoiceTyper

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Apple Silicon MLX](https://img.shields.io/badge/Apple%20Silicon-Metal%20MLX-000000.svg?logo=apple&logoColor=white)](https://github.com/ml-explore/mlx)
[![Windows 10/11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6.svg?logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**VoiceTyper** is an ultra-low-latency, 100% private, self-hosted push-to-talk voice typing system designed for dual-setup workflows (Windows PC + Apple Silicon Mac).

Hold your push-to-talk key (default: `Pause`), speak into your microphone, release the key, and have your speech transcribed and pasted into **any active input field** across Windows (Telegram, Notion, VS Code, Word, web browser, etc.) within **~150–200ms**.

---

## 💡 Why VoiceTyper? (Motivation)

Like many developers and knowledge workers, I work on a powerful **Windows PC** workstation, but I also have an **Apple Silicon Mac (Mac mini M1)** on the same local network. 

I loved the effortless experience of tools like **Wispr Flow** and **Willow Voice**, but I ran into several major drawbacks:
1. **Expensive Subscriptions:** Commercial dictation tools often charge $15–$30/month.
2. **Privacy Concerns:** Every word you dictate gets sent over the internet to third-party cloud servers.
3. **PC Resource Overhead:** Running large Whisper models locally on a Windows gaming or work PC can hog GPU VRAM and cause micro-stutters during heavy tasks.

**VoiceTyper was built to solve this exact problem:**  
It offloads the heavy neural speech recognition to your idle Mac mini's Apple Silicon unified memory (via Apple MLX on Metal GPU) over your ultra-fast local network. You get **instant, air-gapped, zero-cost push-to-talk dictation everywhere in Windows** with **<200ms latency**.

---

### 📊 Comparison

| Feature | 🎙️ VoiceTyper | 🌐 Wispr Flow / Willow Voice | 🐢 Local Whisper on PC (CPU) |
|---|:---:|:---:|:---:|
| **Cost** | **100% Free & Open Source** | $15–$30 / month | Free |
| **Privacy** | **100% Local LAN (Air-Gapped)** | Cloud servers | Local |
| **Latency** | **~150–200ms (Metal GPU)** | ~500–1500ms (Internet roundtrip) | 1.5–4.0s (CPU lag) |
| **PC Performance Impact** | **0% (Offloaded to Mac)** | 0% (Cloud) | High CPU/GPU load |
| **Cold-Start Lag** | **0 ms (Pre-warmed in VRAM)** | Varies | 3–5 seconds |
| **Custom Vocabulary (`initial_prompt`)** | **Yes (Full custom control)** | Limited | Depends on implementation |

---

## 🎨 Note from the Author (The "Vibe Coder" Disclaimer)

> **👋 Hey there!**  
> I am not a 20-year veteran C++/systems engineer — I am a passionate builder and **"vibe coder"** who created VoiceTyper to scratch my own daily itch and solve a real workflow bottleneck between my Windows PC and Mac mini M1.
>
> The codebase is built with modern AI-assisted engineering: it is pragmatic, clean, thoroughly tested in real-world daily use, and designed to **just work**. 
>
> If you find a bug, have an optimization idea, or want to add a feature — please be kind! Pull Requests, code reviews, and constructive feedback are warmly welcomed and appreciated. Let's make voice typing accessible to everyone together! ❤️

---

## ✨ Key Features

- **⚡ Ultra-Low End-to-End Latency (<200ms):**
  - **Apple MLX Metal GPU Engine:** Runs quantized and turbo Whisper models (`large-v3-turbo`) directly on Apple Silicon unified memory.
  - **Server Warm-Up:** Pre-warms model weights in VRAM and compiles Metal computational shaders on daemon startup (**0ms cold start**).
  - **Raw PCM Streaming:** Sends raw `float32 PCM` audio directly in the HTTP body via `/transcribe_raw` without WAV container encoding/decoding overhead.
  - **HTTP Keep-Alive Connection Pool:** Eliminates per-request TCP three-way handshakes.
  - **Continuous Audio Capture:** Eliminates device re-initialization and PortAudio driver overhead.
  - **Atomic Win32 Paste:** Instantly emulates `Ctrl+V` using Win32 API without artificial delays.
- **🎯 Custom Vocabulary Biasing (`initial_prompt`):** Guide Whisper to accurately transcribe specific names, homophones, dialects, and technical terminology (e.g. specialized regional words).
- **🖥️ Silent Windows Background Mode & System Tray:** Discreet tray icon with automatic live heartbeat polling showing real-time status (Ready, Recording, Processing, Offline) and autostart toggle.
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
