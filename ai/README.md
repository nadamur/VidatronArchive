# Vidatron - Healthy Lifestyle Voice Assistant

A voice-activated AI assistant focused on healthy living and wellness, built with local AI for privacy and cloud AI for complex questions.

## Features

- **Wake word activation**: Say "Hey Veedatron" to activate
- **Local AI**: Fast responses using Ollama (qwen2.5:1.5b)
- **Cloud AI**: Complex questions routed to Kimi K2
- **Tools**: Weather, news, time, jokes, system status
- **Text-to-speech**: Natural voice responses with Piper TTS
- **Follow-up mode**: Continue conversations without wake word

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
# openWakeWord: tflite-runtime is not on PyPI for Python 3.12+ / many ARM builds — use ONNX path:
pip install "openwakeword>=0.5.0" --no-deps
```

### 2. Download Models

**Whisper (Speech-to-Text):**
```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make
./models/download-ggml-model.sh base.en
cd ..
```

**Wake Word Model:**
```bash
mkdir -p models/wake_word
# Download Hey_veedatron.onnx to models/wake_word/
```

**Piper Voice:**
```bash
mkdir -p piper/voices
# Download en_GB-semaine-medium.onnx to piper/voices/
```

### 3. Install Ollama

```bash
# macOS
brew install ollama

# Start Ollama
ollama serve

# Pull the model
ollama pull qwen2.5:1.5b
```

### 4. Configure API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys:
# - MOONSHOT_API_KEY (optional, for cloud AI)
# - OPENWEATHER_API_KEY (optional, for weather)
# - NEWSAPI_KEY (optional, for news)
```

### 5. Run

The test UI uses **Kivy** for the window. TTS and filler audio play via **`aplay`** (install `alsa-utils` on Linux).

```bash
python test_ui.py
```

## Usage

1. Say **"Hey Veedatron"** to activate
2. Ask your question
3. Wait for the response
4. Ask follow-up questions (no wake word needed for 8 seconds)

### Example Commands

- "What time is it?"
- "What's the weather in New York?"
- "Tell me a joke"
- "What's the news?"
- "Who are you?"
- "Explain quantum physics" (routes to cloud AI)

## Project Structure

```
vidatron/
├── test_ui.py          # Main UI with voice assistant
├── config.py           # Configuration management
├── orchestrator.py     # Core orchestration logic
├── brain/              # AI routing and tools
│   ├── router.py       # Query routing logic
│   ├── ollama_client.py
│   ├── cloud_client.py
│   └── tools/          # Weather, news, time, etc.
├── audio/              # Speech processing
├── senses/             # Wake word detection
├── assets/             # Face images and filler audio
└── config/             # Soul files (personality)
```

## License

MIT
