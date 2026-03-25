"""Ensure openWakeWord ONNX feature assets exist (wheel often omits resources/models)."""

from pathlib import Path

import openwakeword
from openwakeword.utils import download_models


def ensure_openwakeword_resources() -> None:
    melspec = Path(openwakeword.__file__).parent / "resources" / "models" / "melspectrogram.onnx"
    if not melspec.is_file():
        print("  Downloading openWakeWord feature models (melspectrogram, embedding, VAD) …")
        # Dummy name skips downloading every bundled wake-word pack; feature + VAD still install.
        download_models(model_names=["__skip_official__"])
