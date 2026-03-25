#!/usr/bin/env bash
# ==============================================================
#  Jansky — One-Command Installer for Raspberry Pi 5
# ==============================================================
#  Usage:  chmod +x setup.sh && ./setup.sh
#
#  What this script does (in order):
#   1. Installs system packages (apt)
#   2. Creates a Python 3.13 virtual environment
#   3. Installs Python dependencies (pip)
#   4. Installs Ollama and pulls Qwen 2.5:1.5b
#   5. Builds Whisper.cpp from source and downloads the model
#   6. Downloads the Piper TTS voice
#   7. Reminds you to add API keys
# ==============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── colours ───────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── 1. System packages ───────────────────────────────────────
info "Installing system packages …"
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils
ok "System packages installed"

# ── 2. Python virtual environment ────────────────────────────
VENV_DIR="venv313"
if [ ! -d "$VENV_DIR" ]; then
  info "Creating Python virtual environment …"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
ok "Virtual environment ready ($VENV_DIR)"

# ── 3. Python dependencies ───────────────────────────────────
info "Installing Python packages …"
# openWakeWord declares tflite-runtime on Linux; no Py3.12+/ARM wheels — install deps first, then --no-deps
pip install -q \
  httpx \
  sounddevice \
  numpy \
  scipy \
  piper-tts \
  onnxruntime \
  kivy \
  tqdm \
  scikit-learn \
  python-dotenv
pip install -q "openwakeword>=0.5.0" --no-deps
# Wheel does not always ship resources/models/*.onnx — pull feature + VAD assets from GitHub releases
info "Downloading openWakeWord feature models (melspectrogram, embedding, VAD) …"
python -c "from openwakeword.utils import download_models; download_models(model_names=['__skip_official__'])"
ok "Python packages installed"

# ── 4. Ollama + model ────────────────────────────────────────
# Large binary download often fails on slow/unstable links — retry a few times.
if ! command -v ollama &>/dev/null; then
  OLLAMA_INSTALLED=0
  for attempt in 1 2 3 4 5; do
    info "Installing Ollama (attempt ${attempt}/5) …"
    if curl -fsSL --retry 5 --retry-delay 8 --retry-connrefused \
        https://ollama.com/install.sh | sh; then
      OLLAMA_INSTALLED=1
      break
    fi
    if [ "$attempt" -lt 5 ]; then
      info "Install script failed or download interrupted — waiting 25s before retry …"
      sleep 25
    fi
  done
  if [ "$OLLAMA_INSTALLED" != 1 ]; then
    fail "Ollama install failed after 5 attempts (unstable network / partial download). When stable: curl -fsSL https://ollama.com/install.sh | sh  then: ollama pull qwen2.5:1.5b"
  fi
fi
ok "Ollama installed"

info "Pulling Qwen 2.5:1.5b (this may take a few minutes) …"
for attempt in 1 2 3; do
  if ollama pull qwen2.5:1.5b; then
    break
  fi
  if [ "$attempt" -lt 3 ]; then
    info "Model pull failed — retrying in 20s …"
    sleep 20
  else
    fail "ollama pull qwen2.5:1.5b failed. Fix network, then: ollama pull qwen2.5:1.5b"
  fi
done
ok "Qwen 2.5:1.5b ready"

# ── 5. Whisper.cpp ───────────────────────────────────────────
if [ ! -f "/usr/local/bin/whisper-cpp" ]; then
  if [ ! -d "whisper.cpp" ]; then
    info "Cloning Whisper.cpp …"
    git clone https://github.com/ggerganov/whisper.cpp.git
  fi
  info "Building Whisper.cpp …"
  cd whisper.cpp
  cmake -B build
  cmake --build build --config Release -j"$(nproc)"
  sudo cp build/bin/whisper-cli /usr/local/bin/whisper-cpp
  ok "Whisper.cpp built and installed to /usr/local/bin/whisper-cpp"

  info "Downloading Whisper base.en model …"
  bash models/download-ggml-model.sh base.en
  if [ -f build/bin/quantize ]; then
    ./build/bin/quantize models/ggml-base.en.bin models/ggml-base.en-q5_0.bin q5_0
    ok "Whisper model quantised (q5_0)"
  fi
  cd "$SCRIPT_DIR"
else
  ok "Whisper.cpp already installed"
fi

# ── 6. Piper TTS voice ──────────────────────────────────────
VOICE_DIR="piper/voices"
VOICE_FILE="$VOICE_DIR/en_GB-semaine-medium.onnx"
if [ ! -f "$VOICE_FILE" ]; then
  info "Downloading Piper TTS voice …"
  mkdir -p "$VOICE_DIR"
  wget -q -O "$VOICE_FILE" \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
  wget -q -O "${VOICE_FILE}.json" \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json
  ok "Piper voice downloaded"
else
  ok "Piper voice already present"
fi

# ── 7. .env file ─────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  info "Created .env from template — edit it to add your API keys"
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Jansky is installed!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo "  Next steps:"
echo "    1. (Optional) Add API keys:  nano .env"
echo "    2. Start Jansky:"
echo "         source venv313/bin/activate"
echo "         python orchestrator.py"
echo ""
echo "  Say \"Hey Jansky\" and start talking!"
echo ""
