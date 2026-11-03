"""ElevenLabs comparison track for the podcast POC (same script, same voice brief as Gemini D1).

Reads the key from `elevenlabs_key` (or ELEVENLABS_API_KEY). Pure urllib, no extra dependency.

  python podcast/elevenlabs_tts.py design                      # Voice Design (eleven_ttv_v3): 3 previews, all 3 saved as EL0..EL2
  python podcast/elevenlabs_tts.py audition                    # audition line: each saved voice x {eleven_v3, eleven_v4}
                                                               #   -> out/podcast/audition/EL{n}_{model}.wav (same folder as Gemini clips)
  python podcast/compare_voices.py out/podcast/audition/*.wav  # rank Gemini and ElevenLabs together
  python podcast/elevenlabs_tts.py episode --voice EL1 --model eleven_v4   # -> out/podcast/segments/EL/
  python podcast/make_podcast.py master --voice EL
  python podcast/qa_episode.py EL

API notes checked against the docs on 2026-11-03:
- Voice Design: POST /v1/text-to-voice/design, body {voice_description, model_id, text (100-1000 chars), guidance_scale, seed},
  output_format is a QUERY parameter; previews carry audio_base_64 + generated_voice_id.
- Save: POST /v1/text-to-voice {voice_name, voice_description, generated_voice_id} -> voice_id.
- TTS: POST /v1/text-to-speech/{voice_id}?output_format=pcm_24000, body {text, model_id, language_code, voice_settings, seed}.
- eleven_v3 (5,000 chars) and eleven_v4 (10,000 chars) both list Mandarin (zh). Neither supports <break>;
  pauses come from punctuation/ellipses, emotion from [laughs] [sighs] style tags.
"""
import argparse, base64, json, os, re, sys, time, urllib.error, urllib.request, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "podcast"
SCRIPT = ROOT / "podcast" / "script" / "ep01.json"
API = "https://api.elevenlabs.io"
SR = 24000
CHARS_PER_SEC = 4.5
OK_RATIO = (0.6, 1.6)
MODELS = ["eleven_v3", "eleven_v4"]
BRIEF = ("A Taiwanese man in his mid-thirties speaking Taiwan Mandarin with a natural Taiwanese accent, "
         "no Beijing retroflex or erhua. Low, warm, magnetic voice with a slight rasp and breathiness. "
         "Relaxed and laid-back, like a late-night tech podcast host chatting with a friend, "
         "occasionally self-deprecating. Mixes English tech terms naturally.")
PREVIEW_TEXT = ("欸，大家好，歡迎收聽深夜 Debug，一個在半夜幫你把 bug 跟腦袋一起清一清的節目。我跟你講，"
                "那個讓 app 保持零 crash 聽起來很帥齁，但他得先讓 Claude 自己抓 crash report，"
                "知道哪個版本對應哪個 git commit，還要給它 Windows、macOS、Linux 三台電腦。"
                "所以這不是 prompt，這是一張帳單啦。")
# Gemini inline tags -> ElevenLabs v3/v4 equivalents. Pauses become ellipses (no <break> support).
TAGS = {"<laugh>": "[laughs]", "<sigh>": "[sighs]", "<breath>": "[exhales]", "<short pause>": "……"}


def key():
    k = os.environ.get("elevenlabs_key") or os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        sys.exit("elevenlabs_key is not set in this shell. Add it to the environment settings and start a new session.")
    return k


def call(path, body, accept="application/json", retries=3):
    for attempt in range(retries):
        req = urllib.request.Request(API + path, method="POST", data=json.dumps(body).encode(),
                                     headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            return json.loads(data) if accept == "application/json" else data
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            if e.code in (409, 429, 500, 502, 503) and attempt < retries - 1:
                print(f"  HTTP {e.code}, retrying: {detail[:120]}"); time.sleep(2 ** (attempt + 1)); continue
            sys.exit(f"HTTP {e.code} on {path}: {detail}")


def to_el(text):
    for g, e in TAGS.items():
        text = text.replace(g, e)
    return re.sub(r"<[^>]+>", "", text)


def spoken_chars(text):
    return len(re.sub(r"<[^>]+>|\[[^\]]+\]|[\s，。、！？「」〈〉：；…\.,!?:;]", "", text))


def write_pcm(pcm, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    return len(pcm) / 2 / SR


def registry():
    p = OUT / "elevenlabs" / "voices.json"
    return json.loads(p.read_text()) if p.exists() else {}


def tts(voice_id, text, model, path, settings=None):
    t0 = time.perf_counter()
    pcm = call(f"/v1/text-to-speech/{voice_id}?output_format=pcm_{SR}",
               {"text": text, "model_id": model, "language_code": "zh",
                "voice_settings": settings or {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3}},
               accept="audio/pcm")
    return time.perf_counter() - t0, write_pcm(pcm, path)


def cmd_design(a):
    d = OUT / "elevenlabs"; d.mkdir(parents=True, exist_ok=True)
    if registry():
        print("voices already designed:", registry()); return
    r = call("/v1/text-to-voice/design?output_format=mp3_44100_128",
             {"voice_description": BRIEF, "text": PREVIEW_TEXT, "model_id": "eleven_ttv_v3", "seed": 20261103})
    reg = {}
    for i, p in enumerate(r["previews"]):
        (d / f"preview_EL{i}.mp3").write_bytes(base64.b64decode(p["audio_base_64"]))
        v = call("/v1/text-to-voice", {"voice_name": f"深夜Debug host EL{i} (POC)", "voice_description": BRIEF,
                                       "generated_voice_id": p["generated_voice_id"]})
        reg[f"EL{i}"] = {"voice_id": v["voice_id"], "generated_voice_id": p["generated_voice_id"],
                         "preview_secs": p.get("duration_secs"), "language": p.get("language")}
        print(f"EL{i} saved voice_id={v['voice_id']} preview={p.get('duration_secs')}s lang={p.get('language')}")
    (d / "voices.json").write_text(json.dumps({**reg, "_brief": BRIEF}, ensure_ascii=False, indent=1))


def cmd_audition(a):
    sc = json.loads(SCRIPT.read_text(encoding="utf-8")); text = to_el(sc["audition_text"])
    for name, v in registry().items():
        if name.startswith("_"): continue
        for m in MODELS:
            p = OUT / "audition" / f"{name}_{m}.wav"
            wall, dur = tts(v["voice_id"], text, m, p)
            print(f"{p.name:24s} wall={wall:5.1f}s audio={dur:5.1f}s")


def cmd_episode(a):
    sc = json.loads(SCRIPT.read_text(encoding="utf-8"))
    vid = registry()[a.voice]["voice_id"]; d = OUT / "segments" / "EL"; log = []
    for s in sc["segments"]:
        text = to_el(s["text"]); expected = spoken_chars(s["text"]) / CHARS_PER_SEC
        for attempt in range(1, a.retries + 2):
            wall, dur = tts(vid, text, a.model, d / f"{s['id']}.wav")
            ratio = dur / expected; ok = OK_RATIO[0] <= ratio <= OK_RATIO[1]
            print(f"{s['id']:16s} try{attempt} wall={wall:5.1f}s audio={dur:5.1f}s expected~{expected:5.1f}s ratio={ratio:4.2f} {'OK' if ok else 'RETRY'}")
            if ok: break
        log.append({"id": s["id"], "attempts": attempt, "audio_s": round(dur, 2), "expected_s": round(expected, 1),
                    "ratio": round(ratio, 2), "ok": ok, "wall_s": round(wall, 1), "chars": len(text)})
    (d / "log.json").write_text(json.dumps({"voice": a.voice, "model": a.model, "segments": log}, ensure_ascii=False, indent=1))
    bad = [r["id"] for r in log if not r["ok"]]
    print("all segments OK" if not bad else f"FAILED after retries: {bad}")
    print("total characters billed ~", sum(r["chars"] for r in log))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("design"); sub.add_parser("audition")
    p = sub.add_parser("episode"); p.add_argument("--voice", required=True); p.add_argument("--model", default="eleven_v4"); p.add_argument("--retries", type=int, default=2)
    a = ap.parse_args()
    {"design": cmd_design, "audition": cmd_audition, "episode": cmd_episode}[a.cmd](a)
