from __future__ import annotations

import asyncio
import base64
import io
import warnings
from typing import Any

import soundfile as sf

from helpers import plugins
from helpers.notification import (
    NotificationManager,
    NotificationPriority,
    NotificationType,
)
from helpers.print_style import PrintStyle
from plugins._kokoro_tts.helpers import migration


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


PLUGIN_NAME = "_kokoro_tts"
DEFAULT_CONFIG = {
    "voice": "am_puck",
    "speed": 1.1,
}

_pipeline = None
is_updating_model = False


def normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        return normalized

    voice = str(config.get("voice", normalized["voice"]) or "").strip()
    if voice:
        normalized["voice"] = voice

    try:
        speed = float(config.get("speed", normalized["speed"]))
        if speed > 0:
            normalized["speed"] = speed
    except (TypeError, ValueError):
        pass

    return normalized


def get_config() -> dict[str, Any]:
    config = plugins.get_plugin_config(PLUGIN_NAME) or {}
    return normalize_config(config)


def is_globally_enabled() -> bool:
    migration.ensure_migrated()
    return plugins.determined_toggle_from_paths(
        True, reversed(plugins.get_plugin_roots(PLUGIN_NAME))
    )


async def preload(config: dict[str, Any] | None = None):
    return await _preload()


async def _preload():
    global _pipeline, is_updating_model

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _pipeline:
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Loading Kokoro TTS model...",
                display_time=99,
                group="kokoro-preload",
            )
            PrintStyle.standard("Loading Kokoro TTS model...")
            from kokoro import KPipeline

            _pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Kokoro TTS model loaded.",
                display_time=2,
                group="kokoro-preload",
            )
    finally:
        is_updating_model = False


async def is_downloading() -> bool:
    return is_updating_model


async def is_downloaded() -> bool:
    return _pipeline is not None


def _parse_blend_voice_string(voice: str) -> list[dict] | None:
    """Parse blend format strings like '0.7*bf_emma + 0.3*af_nicole'."""
    if "*" not in voice:
        return None
    parts = voice.split("+")
    blend_voices = []
    for part in parts:
        part = part.strip()
        if "*" not in part:
            continue
        weight_str, name = part.split("*", 1)
        try:
            weight = float(weight_str.strip())
        except ValueError:
            continue
        name = name.strip()
        if name and weight > 0:
            blend_voices.append({"voice": name, "weight": weight})
    return blend_voices if blend_voices else None


def _voices_to_native_blend(blend_voices: list[dict]) -> str:
    """Convert weighted blend voices to native Kokoro comma-separated format.

    Kokoro's KPipeline accepts comma-separated voice names and blends them
    internally at the tensor/style level. Voices are repeated proportionally
    to their weights (e.g. 0.8*A + 0.2*B → A,A,A,A,B).
    """
    voice_parts: list[str] = []
    for item in blend_voices:
        v = str(item["voice"])
        w = float(item["weight"])
        if not v or w <= 0:
            continue
        count = max(1, round(w * 5))  # scale factor 5 gives good granularity
        voice_parts.extend([v] * count)
    return ",".join(voice_parts) if voice_parts else ""


async def synthesize_sentences(
    sentences: list[str], config: dict[str, Any] | None = None
) -> str:
    cfg = normalize_config(config or get_config())
    voice = str(cfg["voice"])

    # Detect blend format and convert to native Kokoro comma-separated voices
    blend = _parse_blend_voice_string(voice)
    if blend:
        voice = _voices_to_native_blend(blend)

    return await _synthesize_sentences(
        sentences,
        voice=voice,
        speed=float(cfg["speed"]),
    )


async def _synthesize_sentences(
    sentences: list[str], *, voice: str, speed: float
) -> str:
    await _preload()

    combined_audio: list[float] = []

    try:
        for sentence in sentences:
            if not sentence.strip():
                continue

            segments = _pipeline(sentence.strip(), voice=voice, speed=speed)  # type: ignore[misc]
            for segment in list(segments):
                audio_tensor = segment.audio
                audio_numpy = audio_tensor.detach().cpu().numpy()  # type: ignore[union-attr]
                combined_audio.extend(audio_numpy.tolist())

        if not combined_audio:
            return ""

        buffer = io.BytesIO()
        sf.write(buffer, combined_audio, 24000, format="WAV")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        PrintStyle.error(f"Error in Kokoro TTS synthesis: {e}")
        raise
