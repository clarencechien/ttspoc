"""Shared helpers for the Gemini 3.8 TTS experiments.

Reads the API key from GEMINI_API_KEY or gemini_key. All synthesis goes through the
Interactions API (the only entry point for the 3.8 TTS models).
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import wave
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable

from google import genai

MODELS = {
    "flash": "gemini-3.8-flash-tts",
    "lite": "gemini-3.8-flash-lite-tts",
}
OUT = Path(__file__).resolve().parent.parent / "out"  # repo-root/out regardless of cwd
SAMPLE_RATE = 24000
# Measured in the pilot: ~32 audio tokens per second of output (429 tok / 13.4 s).
AUDIO_TOKENS_PER_SEC = 32.0
# USD per 1M tokens, launch pricing valid through 2026-12-31 (doubles 2027-01-01).
PRICE = {
    "flash": {"text_in": 0.50, "audio_out": 9.00, "audio_out_batch": 4.50},
    "lite": {"text_in": 0.50, "audio_out": 6.00, "audio_out_batch": 3.00},
}


def client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("gemini_key")
    if not key:
        raise SystemExit("set GEMINI_API_KEY (or gemini_key)")
    return genai.Client(api_key=key)


def text_part(text: str, style: str | None = None, speaker: str | None = None) -> dict:
    ann: dict = {"type": "speech_metadata"}
    if style:
        ann["style"] = style
    if speaker:
        ann["speaker"] = speaker
    return {"type": "text", "text": text, "annotations": [ann]}


def wav_bytes_to_duration(b: bytes) -> float:
    with wave.open(io.BytesIO(b)) as w:
        return w.getnframes() / w.getframerate()


def pcm_to_wav(pcm: bytes, path: Path, sr: int = SAMPLE_RATE) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


@dataclass
class SynthResult:
    model: str
    mode: str  # unary | stream
    wall_s: float
    ttfb_s: float | None
    audio_s: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    chunks: int | None = None
    path: str | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def rtf(self) -> float | None:
        return self.wall_s / self.audio_s if self.audio_s else None

    def row(self) -> dict:
        d = asdict(self)
        d["rtf"] = self.rtf
        return d


def synthesize(
    c: genai.Client,
    model: str,
    parts: list[dict],
    speech_config,
    out_path: Path | None = None,
    stream: bool = False,
    mime_type: str | None = None,
    sample_rate: int | None = None,
) -> SynthResult:
    """Synthesize one request. `speech_config` is either [{"voice": id}] for a
    single speaker, or {"mode": "conversational", "speakers": [...]} for two speakers."""
    response_format: dict = {"type": "audio"}
    if mime_type:
        response_format["mime_type"] = mime_type
    if sample_rate:
        response_format["sample_rate"] = sample_rate
    kwargs = dict(
        model=model,
        input=[{"type": "user_input", "content": parts}],
        response_format=response_format,
        generation_config={"speech_config": speech_config},
    )
    t0 = time.perf_counter()
    try:
        if not stream:
            r = c.interactions.create(**kwargs)
            wall = time.perf_counter() - t0
            d = r.model_dump()
            audio = base64.b64decode(d["output_audio"]["data"])
            usage = d.get("usage") or {}
            dur = wav_bytes_to_duration(audio) if (mime_type in (None, "audio/wav")) else len(audio) / 2 / (sample_rate or SAMPLE_RATE)
            if out_path:
                out_path.write_bytes(audio)
            return SynthResult(model, "unary", wall, None, dur,
                               usage.get("total_input_tokens"), usage.get("total_output_tokens"),
                               None, str(out_path) if out_path else None,
                               extra={"mime_type": d["output_audio"].get("mime_type")})
        first = None
        chunks: list[bytes] = []
        usage = {}
        for ev in c.interactions.create(stream=True, **kwargs):
            d = ev.model_dump()
            et = d.get("event_type")
            if et == "step.delta" and (d.get("delta") or {}).get("type") == "audio":
                if first is None:
                    first = time.perf_counter() - t0
                chunks.append(base64.b64decode(d["delta"]["data"]))
            elif et == "interaction.completed":
                usage = ((d.get("interaction") or {}).get("usage")) or {}
        wall = time.perf_counter() - t0
        pcm = b"".join(chunks)
        sr = sample_rate or SAMPLE_RATE
        dur = len(pcm) / 2 / sr
        if out_path:
            pcm_to_wav(pcm, out_path, sr)
        return SynthResult(model, "stream", wall, first, dur,
                           usage.get("total_input_tokens"), usage.get("total_output_tokens"),
                           len(chunks), str(out_path) if out_path else None)
    except Exception as e:  # noqa: BLE001 - we want every failure recorded, not raised
        return SynthResult(model, "stream" if stream else "unary", time.perf_counter() - t0, None, 0.0,
                           error=f"{type(e).__name__}: {str(e)[:300]}")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def cost_usd(model_key: str, text_tokens: int, audio_tokens: int, batch: bool = False) -> float:
    p = PRICE[model_key]
    out_rate = p["audio_out_batch"] if batch else p["audio_out"]
    return text_tokens / 1e6 * p["text_in"] + audio_tokens / 1e6 * out_rate
