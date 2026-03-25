"""
Configuration management for Jansky.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json


@dataclass
class Config:
    """Application configuration."""

    # Paths - dynamically set based on this file's location
    project_root: str = ""
    assets_path: str = ""

    # Audio - Piper TTS (using piper-tts Python package)
    piper_voice: str = ""

    # Whisper.cpp
    whisper_path: str = "/usr/local/bin/whisper-cpp"
    whisper_model: str = ""

    # Models
    chat_model: str = "qwen2.5:1.5b"

    # Wake word
    wake_word_model: str = ""
    wake_word_threshold: float = 0.5

    # Microphone settings (for USB mics that may have different sample rates)
    mic_sample_rate: int = 48000

    # Local location default
    local_location: str = "Kingston, CA"
    target_sample_rate: int = 16000

    # API Keys (loaded from environment)
    openweather_api_key: str = ""
    moonshot_api_key: str = ""
    groq_api_key: str = ""
    newsapi_key: str = ""

    # Groq chat model id (e.g. llama-3.3-70b-versatile)
    groq_model: str = ""

    # Spotify Web API (optional — voice: "play …", "pause music"; see setup_spotify_token.py)
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_refresh_token: str = ""
    spotify_device_id: str = ""

    # Soul/personality files
    local_soul_path: str = ""
    cloud_soul_path: str = ""

    # Editable JSON: name, music prefs, notes (see data/user_profile.json)
    user_profile_path: str = ""

    # Display
    display_width: int = 800
    display_height: int = 480
    use_framebuffer: bool = False

    # Features
    enable_streaming_tts: bool = False
    enable_ui: bool = False
    
    def __post_init__(self):
        """Set default paths based on project location."""
        if not self.project_root:
            self.project_root = str(Path(__file__).parent)
        if not self.assets_path:
            self.assets_path = os.path.join(self.project_root, "assets", "face")
        if not self.piper_voice:
            self.piper_voice = os.path.join(self.project_root, "piper", "voices", "en_GB-semaine-medium.onnx")
        local_whisper_cli = os.path.join(
            self.project_root, "whisper.cpp", "build", "bin", "whisper-cli"
        )
        if os.path.isfile(local_whisper_cli):
            self.whisper_path = local_whisper_cli
        if not self.whisper_model:
            self.whisper_model = os.path.join(
                self.project_root, "whisper.cpp", "models", "ggml-base.en.bin"
            )
        if not self.wake_word_model:
            self.wake_word_model = os.path.join(self.project_root, "models", "wake_word", "Hey_veedatron.onnx")
        if not self.local_soul_path:
            self.local_soul_path = os.path.join(self.project_root, "config", "local_soul.md")
        if not self.cloud_soul_path:
            self.cloud_soul_path = os.path.join(self.project_root, "config", "cloud_soul.md")

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file and environment."""
        config = cls()

        # Load from JSON file if exists
        if config_path is None:
            # Use the actual location of this file to find config.json
            this_dir = Path(__file__).parent
            config_path = os.path.join(this_dir, "config", "config.json")

        if Path(config_path).exists():
            with open(config_path) as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # Load from .env file if present
        env_path = os.path.join(config.project_root, ".env")
        if Path(env_path).exists():
            config._load_env_file(env_path)

        # Override with environment variables
        config.openweather_api_key = os.getenv(
            "OPENWEATHER_API_KEY",
            config.openweather_api_key
        )
        config.moonshot_api_key = os.getenv(
            "MOONSHOT_API_KEY",
            config.moonshot_api_key
        )
        config.groq_api_key = os.getenv(
            "GROQ_API_KEY",
            config.groq_api_key
        )
        config.groq_model = os.getenv(
            "GROQ_MODEL",
            config.groq_model or "llama-3.3-70b-versatile",
        )
        config.newsapi_key = os.getenv(
            "NEWSAPI_KEY",
            config.newsapi_key
        )
        config.spotify_client_id = os.getenv(
            "SPOTIFY_CLIENT_ID",
            config.spotify_client_id,
        )
        config.spotify_client_secret = os.getenv(
            "SPOTIFY_CLIENT_SECRET",
            config.spotify_client_secret,
        )
        config.spotify_refresh_token = os.getenv(
            "SPOTIFY_REFRESH_TOKEN",
            config.spotify_refresh_token,
        )
        config.spotify_device_id = os.getenv(
            "SPOTIFY_DEVICE_ID",
            config.spotify_device_id,
        )
        config.user_profile_path = os.getenv(
            "VIDATRON_USER_PROFILE",
            config.user_profile_path,
        )

        return config

    def _load_env_file(self, path: str):
        """Load environment variables from .env file."""
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    def save(self, config_path: Optional[str] = None):
        """Save configuration to file."""
        if config_path is None:
            config_path = os.path.join(self.project_root, "config", "config.json")

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        # Don't save API keys to file
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_api_key") and not k.endswith("_key")
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
