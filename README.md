# 🎙️ VoiceTyper

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Apple Silicon MLX](https://img.shields.io/badge/Apple%20Silicon-Metal%20MLX-000000.svg?logo=apple&logoColor=white)](https://github.com/ml-explore/mlx)
[![Windows 10/11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6.svg?logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**VoiceTyper** is a 100% free, private, self-hosted push-to-talk voice typing & AI translation system designed for dual-machine setups (Windows PC + Apple Silicon Mac).

Hold your push-to-talk key (default: `Pause`), speak into your microphone, release the key, and have your speech transcribed and pasted into **any active input field** across Windows (Telegram, Notion, VS Code, Word, web browser, etc.) using hardware-accelerated OpenAI Whisper inference running on an Apple Silicon (Mac mini / MacBook M1/M2/M3/M4) local server.

---

## 💡 Why VoiceTyper? (Motivation)

Like many developers and knowledge workers, I work primarily on a **Windows PC** workstation, but I also have an **Apple Silicon Mac (Mac mini M1)** on the same local network.

I loved the effortless experience of commercial tools like **Wispr Flow** and **Willow Voice**, but I ran into several major drawbacks:
1. **Expensive Monthly Subscriptions:** Commercial dictation tools charge $15–$30/month.
2. **Privacy Concerns:** Every word you dictate gets streamed to third-party cloud servers.
3. **PC Resource Overhead:** Running large Whisper models locally on a Windows gaming or work PC can hog GPU VRAM and cause micro-stutters during heavy tasks.

**VoiceTyper was built to solve this exact dilemma:**  
It offloads speech recognition to your idle Mac mini's Apple Silicon unified memory (via Apple MLX on Metal GPU) over your local network. You get **instant, air-gapped, zero-cost push-to-talk dictation everywhere in Windows** with **zero cloud dependencies and zero impact on your PC performance**.

---

### 📊 Honest Comparison & Real Latency

| Feature | 🎙️ VoiceTyper | 🌐 Wispr Flow / Willow Voice | 🐢 Local Whisper on PC (CPU) |
|---|:---:|:---:|:---:|
| **Cost** | **100% Free & Open Source** | $15–$30 / month | Free |
| **Privacy** | **100% Local LAN (Air-Gapped)** | Cloud servers | Local |
| **Real Latency (Mac M1)** | **~350ms (`small`) / ~1.2s (`large-turbo`)** | ~300–600ms (H100 Datacenter GPUs) | 2.5–5.0s (CPU lag) |
| **PC Performance Impact** | **0% (Offloaded to Mac)** | 0% (Cloud) | High CPU/GPU load |
| **Voice Translation** | **Yes (Local LLM via Ollama)** | Cloud | No |
| **Custom Replacements** | **Yes (Regex & Word Rules)** | Limited | Depends on setup |

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

- **⚡ Hardware Accelerated Local Inference:**
  - **Apple MLX Metal GPU Engine:** Runs Whisper models (`small`, `medium`, `large-v3-turbo`) directly on Apple Silicon unified memory.
  - **Server Warm-Up:** Pre-warms model weights in VRAM and compiles Metal shaders on startup (**0ms cold start**).
  - **Raw PCM Streaming:** Sends raw `float32 PCM` audio via `/transcribe_raw` without WAV overhead.
  - **Single Instance Windows Mutex:** Prevents duplicate background processes and double-paste glitches.
- **🌐 Voice-Activated Translation:**
  - Say *«Переведи на немецкий: добрый день, я скоро буду»* or *«Translate to Spanish: Thank you very much»* — VoiceTyper automatically translates the sentence via local LLM (Ollama Qwen2.5 on Mac) and pastes the translation directly!
- **🔄 Guaranteed Custom Replacements (`custom_replacements`):**
  - Fix tricky phonetic homophones or domain-specific abbreviations with 100% regex-based precision.
- **🎯 Custom Vocabulary Biasing (`initial_prompt`):** Guide Whisper toward specialized names, regional terminology, and technical jargon.
- **🖥️ Silent Windows Background Mode & System Tray:** Discreet tray icon with automatic live heartbeat polling (Ready, Recording, Processing, Offline).

---

## 🏗️ Architecture

```
┌────────────────────────────────────────┐       Local LAN (HTTP Keep-Alive)       ┌────────────────────────────────────────┐
│             Windows Client             │ ──────────────────────────────────────► │        Apple Silicon Mac Server        │
│                                        │                                         │                                        │
│  [Hold Hotkey (e.g. Pause)]            │                                         │  FastAPI + Apple MLX Metal GPU Engine  │
│  1. Continuous Audio Stream (16kHz)    │ ──── Raw Float32 PCM (/transcribe_raw) ►│  1. Pre-Warmed Whisper (large-v3-turbo)│
│  2. Voice Command & Replacement Parser │                                         │  2. Local LLM Translation (Ollama Qwen)│
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

2. *(Optional for Translation)* Ensure Ollama is running on Mac:
   ```bash
   ollama run qwen2.5:14b
   ```

3. Start the transcription & translation server:
   ```bash
   python3 server_mac.py
   ```

---

### 2. Client Setup (Windows)

1. Install client dependencies:
   ```cmd
   pip install -r requirements-client.txt
   ```

2. Configure connection settings:
   Copy `config.example.json` to `config.json`:
   ```json
   {
     "server_ip": "192.168.1.100",
     "server_port": 9090,
     "hotkey": "pause",
     "model": "large-v3-turbo",
     "language": "ru",
     "initial_prompt": "Optional terminology, domain keywords, or technical acronyms.",
     "custom_replacements": {},
     "translation_enabled": true,
     "paste_method": "unicode",
     "device_keyword": "",
     "sample_rate": 16000
   }
   ```

3. Generate background launcher and shortcuts:
   ```cmd
   python setup_shortcuts.py
   ```

4. Start VoiceTyper:
   - Double-click `Voice Typer` on your Desktop or run `python main.py`.

---

## ⚙️ Configuration Reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `server_ip` | string | `"192.168.1.100"` | IP address of your Mac mini / Whisper server on local network. |
| `server_port` | integer | `9090` | Port of the Whisper HTTP server. |
| `hotkey` | string | `"pause"` | Push-to-talk key (`"pause"`, `"insert"`, `"home"`, `"f8"`, etc.). |
| `model` | string | `"large-v3-turbo"` | Whisper model (`"large-v3-turbo"`, `"small"`, `"medium"`). |
| `language` | string | `"ru"` | Primary transcription language code. |
| `initial_prompt` | string | `""` | Context hint for Whisper to bias recognition. |
| `custom_replacements` | object | `{}` | Key-value regex dictionary for guaranteed word/homophone replacements. |
| `translation_enabled` | boolean | `true` | Enables voice-triggered translation commands (*"Переведи на [язык]: ..."*). |
| `paste_method` | string | `"unicode"` | Text insertion mode (`"unicode"` for instant direct Win32 injection without clipboard/Caramba conflicts, or `"clipboard"` for Ctrl+V). |
| `device_keyword` | string | `""` | Substring to match specific microphone name (empty uses default). |
| `sample_rate` | integer | `16000` | Audio sampling rate (16000 Hz). |

---

## 🎯 Usage & Voice Commands

1. **Standard Push-to-Talk:**
   - Hold `Pause`, speak naturally, release `Pause`. Your speech is typed instantly.
2. **Instant Translation:**
   - Hold `Pause` and say:  
     > *«Переведи на английский: отправь мне пожалуйста финальный счет»*  
     > *«Translate to German: Thank you very much for your help»*  
   - Release `Pause` — VoiceTyper translates the phrase locally using Ollama and inserts the translated text into the active field!

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
