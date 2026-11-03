"""ElevenLabs comparison track for the podcast POC (same script, same voice brief).

Reads the key from the `elevenlabs_key` environment variable (or ELEVENLABS_API_KEY).
Uses only the public REST API through urllib, so no extra dependency is needed.

  python podcast/elevenlabs_tts.py design                # Voice Design: 3 previews from the brief -> pick one -> save
  python podcast/elevenlabs_tts.py episode               # every segment with eleven_v3, pcm 24 kHz -> out/podcast/segments/EL/
  python podcast/make_podcast.py master --voice EL       # same mastering chain as the Gemini version

Notes
- eleven_v3 supports Mandarin and inline audio tags such as [laughs] and [sighs]; the Gemini
  tags <laugh>, <sigh>, <short pause> are converted to their ElevenLabs equivalents.
- The voice brief is the same generic description used for Gemini D1. It names no real person.
"""
import base64, json, os, re, sys, urllib.request, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "podcast"
SCRIPT = ROOT / "podcast" / "script" / "ep01.json"
API = "https://api.elevenlabs.io"
MODEL = "eleven_v3"
SR = 24000
BRIEF = ("A Taiwanese man in his mid-thirties speaking Taiwan Mandarin with a natural Taiwanese accent "
         "(no Beijing retroflex or erhua). Low, warm, magnetic voice with a slight rasp and breathiness. "
         "Relaxed and laid-back, like a late-night tech podcast host chatting with a friend, "
         "occasionally self-deprecating. Mixes English tech terms naturally.")
PREVIEW_TEXT = ("欸，大家好，歡迎收聽深夜 Debug。我跟你講，那個讓 app 保持零 crash 聽起來很帥齁，"
                "但他得先讓 Claude 自己抓 crash report，知道哪個版本對應哪個 git commit，"
                "還要給它 Windows、macOS、Linux 三台電腦。所以這不是 prompt，這是一張帳單啦。")
TAGS = {"<laugh>": "[laughs]", "<sigh>": "[sighs]", "<short pause>": "[short pause]", "<breath>": "[exhales]"}


def key():
    k = os.environ.get("elevenlabs_key") or os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        sys.exit("elevenlabs_key is not set in this shell. Add it to the environment settings and start a new session.")
    return k


def call(path, body=None, method="POST", accept="application/json"):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": accept})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    return json.loads(data) if accept == "application/json" else data


def write_pcm(pcm, path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)


def cmd_design():
    d = OUT / "elevenlabs"; d.mkdir(parents=True, exist_ok=True)
    r = call("/v1/text-to-voice/design", {"voice_description": BRIEF, "text": PREVIEW_TEXT, "model_id": "eleven_ttv_v3",
                                          "output_format": "mp3_44100_128"})
    previews = r["previews"]
    for i, p in enumerate(previews):
        (d / f"preview_{i}.mp3").write_bytes(base64.b64decode(p["audio_base_64"]))
        print(f"preview_{i}.mp3  generated_voice_id={p['generated_voice_id']}")
    pick = int(os.environ.get("EL_PICK", "0"))
    v = call("/v1/text-to-voice", {"voice_name": "深夜 Debug host (POC)", "voice_description": BRIEF,
                                   "generated_voice_id": previews[pick]["generated_voice_id"]})
    (d / "voice.json").write_text(json.dumps({"voice_id": v["voice_id"], "picked_preview": pick, "brief": BRIEF}, indent=1))
    print("saved voice", v["voice_id"], "(set EL_PICK=n to choose another preview)")


def cmd_episode():
    sc = json.loads(SCRIPT.read_text(encoding="utf-8"))
    vid = json.loads((OUT / "elevenlabs" / "voice.json").read_text())["voice_id"]
    d = OUT / "segments" / "EL"; d.mkdir(parents=True, exist_ok=True)
    for s in sc["segments"]:
        text = s["text"]
        for g, e in TAGS.items():
            text = text.replace(g, e)
        text = re.sub(r"<[^>]+>", "", text)
        pcm = call(f"/v1/text-to-speech/{vid}?output_format=pcm_24000",
                   {"text": text, "model_id": MODEL, "language_code": "zh",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3}},
                   accept="audio/pcm")
        write_pcm(pcm, d / f"{s['id']}.wav")
        print(f"{s['id']:16s} {len(pcm)/2/SR:5.1f}s")


if __name__ == "__main__":
    {"design": cmd_design, "episode": cmd_episode}[sys.argv[1]]()
