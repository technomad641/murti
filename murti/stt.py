"""Speech-to-text, local and pluggable.

Two backends, same interface:
  * "mlx"            - MLX Whisper, runs on the Apple Silicon GPU. Default.
  * "faster-whisper" - CTranslate2 on CPU (int8). Portable fallback.

Both auto-detect language (language=None), which is what lets mixed
Hindi/English (code-switched) speech be transcribed in-language.
"""
from __future__ import annotations

import numpy as np

DEFAULT_MODEL = "large-v3-turbo"
MLX_REPO = "mlx-community/whisper-large-v3-turbo"


class STTEngine:
    name = "base"

    def transcribe(self, audio: "np.ndarray | str") -> tuple[str, str | None]:
        raise NotImplementedError


class MLXEngine(STTEngine):
    name = "mlx"

    def __init__(self, repo: str = MLX_REPO):
        import mlx_whisper  # imported lazily so the fallback works without it

        self._mlx = mlx_whisper
        self.repo = repo

    def transcribe(self, audio):
        r = self._mlx.transcribe(audio, path_or_hf_repo=self.repo)
        return r["text"].strip(), r.get("language")


class FasterWhisperEngine(STTEngine):
    name = "faster-whisper"

    def __init__(self, model_name: str = DEFAULT_MODEL, cpu_threads: int = 4):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            model_name, device="cpu", compute_type="int8", cpu_threads=cpu_threads
        )

    def transcribe(self, audio):
        segments, info = self.model.transcribe(
            audio, language=None, beam_size=1, vad_filter=True
        )
        text = "".join(s.text for s in segments).strip()
        return text, info.language


def make_engine(engine: str = "mlx", model_name: str = DEFAULT_MODEL) -> STTEngine:
    """Build an STT engine, falling back to faster-whisper if MLX is unavailable."""
    if engine == "mlx":
        try:
            return MLXEngine()
        except Exception:
            pass  # MLX missing/unsupported -> CPU fallback
    return FasterWhisperEngine(model_name=model_name)
