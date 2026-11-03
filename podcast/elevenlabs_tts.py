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
BRIEF_TW = ("A Taiwanese man in his mid-thirties recording his own tech podcast at home, not a professional voice actor. "
            "Natural Taiwan Mandarin accent as spoken by young people in Taipei: light or no retroflex (shi sounds close to si), "
            "no erhua, -ing and -in sound alike, few neutral tones, syllables run together casually, sentence-final particles "
            "like o, la, ma slightly drawn out. Soft, chatty intonation, not a news-anchor or Beijing broadcast accent. "
            "Low, warm, magnetic voice with chest resonance and a little rasp. Relaxed but clear: tones stay distinct, "
            "every word is easy to understand. Mixes English tech terms the way Taiwanese engineers do.")
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


REG = ROOT / "podcast" / "results" / "elevenlabs" / "voices.json"

def registry():
    return json.loads(REG.read_text(encoding="utf-8")) if REG.exists() else {}


def tts(voice_id, text, model, path, settings=None):
    t0 = time.perf_counter()
    pcm = call(f"/v1/text-to-speech/{voice_id}?output_format=pcm_{SR}",
               {"text": text, "model_id": model, "language_code": "zh",
                "voice_settings": settings or {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3}},
               accept="audio/pcm")
    return time.perf_counter() - t0, write_pcm(pcm, path)


def cmd_design(a):
    d = OUT / "elevenlabs"; d.mkdir(parents=True, exist_ok=True)
    reg = registry(); prefix = a.prefix
    if any(k.startswith(prefix) for k in reg if not k.startswith("_")) and prefix == "EL":
        print("voices already designed:", [k for k in reg if not k.startswith("_")]); return
    brief = BRIEF_TW if a.brief == "tw" else BRIEF
    text = Path(a.preview_file).read_text(encoding="utf-8") if a.preview_file else PREVIEW_TEXT
    text = to_el(text)[:1000]
    r = call("/v1/text-to-voice/design?output_format=mp3_44100_128",
             {"voice_description": brief, "text": text, "model_id": "eleven_ttv_v3", "seed": a.seed})
    start = 1 + max([int(k[len(prefix):]) for k in reg if k.startswith(prefix) and k[len(prefix):].isdigit()], default=-1)
    for i, pv in enumerate(r["previews"]):
        key = f"{prefix}{start + i}"
        (d / f"preview_{key}.mp3").write_bytes(base64.b64decode(pv["audio_base_64"]))
        v = call("/v1/text-to-voice", {"voice_name": f"深夜Debug host {key} (POC)", "voice_description": brief,
                                       "generated_voice_id": pv["generated_voice_id"]})
        reg[key] = {"voice_id": v["voice_id"], "generated_voice_id": pv["generated_voice_id"], "preview_secs": pv.get("duration_secs"),
                    "language": pv.get("language"), "brief": a.brief, "seed": a.seed, "design_model": "eleven_ttv_v3"}
        print(f"{key} saved voice_id={v['voice_id']} preview={pv.get('duration_secs')}s lang={pv.get('language')}")
    reg["_brief_tw"] = BRIEF_TW
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_audition(a):
    sc = json.loads(SCRIPT.read_text(encoding="utf-8")); text = to_el(sc["audition_text"])
    for name, v in registry().items():
        if name.startswith("_"): continue
        for m in MODELS:
            p = OUT / "audition" / f"{name}_{m}.wav"
            wall, dur = tts(v["voice_id"], text, m, p)
            print(f"{p.name:24s} wall={wall:5.1f}s audio={dur:5.1f}s")


def long_pauses(path, min_len=0.6):
    import subprocess
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise=-35dB:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    with wave.open(str(path)) as w:
        dur = w.getnframes() / w.getframerate()
    return sum(1 for t in re.findall(r"silence_start: ([0-9.]+)", r) if 0.2 < float(t) < dur - 0.8), dur


def cmd_episode(a):
    import shutil
    sc = json.loads(Path(a.script or SCRIPT).read_text(encoding="utf-8"))
    vid = registry()[a.voice]["voice_id"]; settings = json.loads(a.settings) if a.settings else None
    d = OUT / "segments" / (f"EL_{a.tag}" if a.tag else "EL"); d.mkdir(parents=True, exist_ok=True); log = []
    for s in sc["segments"]:
        text = (a.prefix_tag + " " if a.prefix_tag else "") + to_el(s["text"]); expected = spoken_chars(s["text"]) / CHARS_PER_SEC
        takes = []
        for k in range(a.takes):
            tp = d / (f"{s['id']}.take{k}.wav" if a.takes > 1 else f"{s['id']}.wav")
            for attempt in range(1, a.retries + 2):
                if tp.exists() and attempt == 1:
                    wall = 0.0
                else:
                    wall, _ = tts(vid, text, a.model, tp, settings)
                lp, dur = long_pauses(tp); ratio = dur / expected; ok = OK_RATIO[0] <= ratio <= OK_RATIO[1]
                print(f"{s['id']:16s} take{k} try{attempt} wall={wall:5.1f}s audio={dur:5.1f}s ratio={ratio:4.2f} pauses>=0.6s={lp} {'OK' if ok else 'RETRY'}")
                if ok: break
                tp.unlink()
            takes.append({"path": tp, "ok": ok, "dur": dur, "ratio": ratio, "pauses": lp})
        best = min(takes, key=lambda t: (not t["ok"], t["pauses"] / max(t["dur"], 1) * 60, t["dur"]))
        if best["path"] != d / f"{s['id']}.wav":
            shutil.copyfile(best["path"], d / f"{s['id']}.wav")
        log.append({"id": s["id"], "audio_s": round(best["dur"], 2), "expected_s": round(expected, 1), "ratio": round(best["ratio"], 2),
                    "ok": best["ok"], "chars": len(text) * a.takes, "chosen": best["path"].name,
                    "takes": [{"file": t["path"].name, "audio_s": round(t["dur"], 1), "pauses_ge_0_6s": t["pauses"]} for t in takes]})
    (d / "log.json").write_text(json.dumps({"voice": a.voice, "model": a.model, "settings": settings, "prefix_tag": a.prefix_tag,
                                            "script": a.script, "segments": log}, ensure_ascii=False, indent=1))
    print("characters billed ~", sum(r["chars"] for r in log))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("design"); p.add_argument("--brief", choices=["generic", "tw"], default="generic")
    p.add_argument("--seed", type=int, default=20261103); p.add_argument("--prefix", default="EL"); p.add_argument("--preview-file")
    sub.add_parser("audition")
    p = sub.add_parser("episode"); p.add_argument("--voice", required=True); p.add_argument("--model", default="eleven_v4")
    p.add_argument("--retries", type=int, default=2); p.add_argument("--script"); p.add_argument("--takes", type=int, default=1)
    p.add_argument("--tag", default=""); p.add_argument("--settings", help='JSON voice_settings, e.g. {"stability":0.5}')
    p.add_argument("--prefix-tag", default="", help="audio tag put before each segment, e.g. [casually]")
    a = ap.parse_args()
    {"design": cmd_design, "audition": cmd_audition, "episode": cmd_episode}[a.cmd](a)
