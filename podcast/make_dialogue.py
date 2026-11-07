"""Two-person dialogue (interview) on Gemini 3.8 TTS and ElevenLabs, three ways.

  python podcast/make_dialogue.py design                      # Gemini designed voices IV_F (interviewer) / IV_M (candidate)
  python podcast/make_dialogue.py gemini-multi --voices I=Kore,C=Achird   # A: one request, built-in voices, |嗯| backchannels
  python podcast/make_dialogue.py gemini-turns --voices I=IV_F,C=IV_M     # B: one request per turn, spliced backchannels + overlap
  python podcast/make_dialogue.py elevenlabs --voices I=<id>,C=<id>       # C: ElevenLabs text-to-dialogue (eleven_v3)
  python podcast/make_dialogue.py patch A.wav A_fixed.wav --start 28.85 --end 30.2 --clip out/dialogue/B_.../turn_04.wav
                                                              # splice a turn the multi-speaker render gave to the wrong voice
  python podcast/make_dialogue.py master out/dialogue/<name>.wav podcast/samples/dialogue/<name>.mp3

Script format (podcast/dialogue/*.json): turns of {speaker, style, text, gap?, overlap?}.
  [[嗯]]   in a turn's text = the *listener* says 嗯 at that point.
           A turns it into Gemini's |嗯| (the model voices the other speaker); B synthesises the
           listener's 嗯 separately and mixes it under the speaker at the nearest pause; C drops it.
  gap      seconds of silence before the turn (default 0.35).
  overlap  seconds the turn starts *before* the previous one ends (an interruption); the previous
           turn is faded out shortly after, as a speaker who is cut off stops talking.
"""
import argparse, base64, json, re, subprocess, sys, wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_podcast import client, TTS_MODEL, SR, registry, measure_lufs, wav_duration

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "dialogue"
REG = ROOT / "podcast" / "results" / "voices.json"
DEFAULT_SCRIPT = ROOT / "podcast" / "dialogue" / "interview_claude_sessions.json"
BC = re.compile(r"\[\[(.+?)\]\]")
CLICK = 0.7      # raw Gemini turns: clean speech peaks at ~0.5 sample-to-sample; the glitches heard were 0.84 and 1.17

DESIGNS = {
    "IV_F": ("面試官", "female",
             "四十出頭的台灣女性技術主管，講標準台灣國語，中低音，聲音沉穩、有威嚴，咬字乾淨俐落，"
             "語氣冷靜克制，不笑也不客套，像在主持一場技術面試。沒有中國大陸的捲舌腔和兒化音。"),
    "IV_M": ("面試者", "male",
             "二十七、八歲的台灣男工程師，講台灣國語，中音、乾淨、偏年輕，說話自然，帶一點書卷氣，"
             "中英夾雜很自然。沒有中國大陸的捲舌腔和兒化音。"),
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_voices(s):
    return dict(kv.split("=", 1) for kv in s.split(","))


def all_voices():
    """Committed registry plus the local out/ copy (registry() returns only the first file it finds)."""
    reg = json.loads(REG.read_text(encoding="utf-8")) if REG.exists() else {}
    return {**registry(), **reg}


def resolve(v):
    """IV_F / D1 -> voice_... id from the registry; anything else (Kore, voice_...) as is."""
    return all_voices().get(v, {}).get("id", v)


def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def write_wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def trim(x, thr_db=-40, pad=0.05):
    """Strip leading/trailing silence so gaps between turns are ours, not the model's."""
    env = np.convolve(np.abs(x), np.ones(240) / 240, mode="same")
    on = np.where(env > 10 ** (thr_db / 20))[0]
    if not len(on):
        return x
    p = int(pad * SR)
    y = x[max(0, on[0] - p): on[-1] + p].copy()
    f = min(int(0.015 * SR), len(y) // 2)      # short fades: a hard cut in the waveform is an audible click
    y[:f] *= np.linspace(0, 1, f); y[len(y) - f:] *= np.linspace(1, 0, f)
    return y


def gain_to(x, target_lufs, tmp):
    write_wav(tmp, x)
    return x * 10 ** ((target_lufs - measure_lufs(tmp)) / 20)


def active_rms(x, thr_db=-40):
    """RMS over voiced 10 ms frames. Works on clips too short for LUFS (gated over 400 ms blocks)."""
    fr = x[: len(x) // 240 * 240].reshape(-1, 240)
    r = np.sqrt((fr ** 2).mean(axis=1))
    r = r[r > 10 ** (thr_db / 20)]
    return float(np.sqrt((r ** 2).mean())) if len(r) else 1e-4


def pauses(x, min_len=0.12, thr_db=-35):
    """Mid-turn pauses as (start, end) seconds."""
    hop = 240
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    quiet = rms < 10 ** (thr_db / 20)
    out, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * hop / SR >= min_len and i > 0 and j < len(quiet):
                out.append((i * hop / SR, j * hop / SR))
            i = j
        else:
            i += 1
    return out


def style_for(sc, turn):
    p = sc["speakers"][turn["speaker"]]
    return f"{p['persona']} 這一句：{turn['style']}。台灣國語口音，自然口語，不要捲舌。"


# ---------------------------------------------------------------- design
def cmd_design(a):
    c = client(); OUT.mkdir(parents=True, exist_ok=True)
    reg = all_voices()
    for key, (name, gender, prompt) in DESIGNS.items():
        if key in reg:
            print("exists", key, reg[key]["id"]); continue
        v = c.voices.create(store=True, voice={
            "model": TTS_MODEL, "type": "prompted", "display_name": f"dialogue-{key}-{name}",
            "gender": gender, "language_code": "zh-TW", "prompted": {"input": prompt}}).model_dump()
        (OUT / f"design_sample_{key}.wav").write_bytes(base64.b64decode(v["sample_audio"]["data"]))
        reg[key] = {"id": v["id"], "name": name, "prompt": prompt, "gender": gender, "expire_time": str(v.get("expire_time"))}
        REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
        print("created", key, v["id"])


# ---------------------------------------------------------------- A: one multi-speaker request
def cmd_gemini_multi(a):
    sc = load(a.script); vo = parse_voices(a.voices); c = client(); OUT.mkdir(parents=True, exist_ok=True)
    names = {k: p["name"] for k, p in sc["speakers"].items()}
    # every text part needs its own speaker annotation (a single "名字：" transcript is rejected:
    # "Multi-speaker interactions must specify a speaker for each text turn")
    sty = (lambda t: style_for(sc, t)) if a.turn_style else \
        (lambda t: sc["speakers"][t["speaker"]]["persona"] + " 台灣國語口音，自然口語，不要捲舌。")
    content = [{"type": "text", "text": BC.sub(r"|\1|", t["text"]),
                "annotations": [{"type": "speech_metadata", "speaker": names[t["speaker"]], "style": sty(t)}]}
               for t in sc["turns"]]
    speakers = [{"speaker": names[k], "voice": resolve(v)} for k, v in vo.items()]
    out = OUT / f"{a.name}.wav"
    r = c.interactions.create(model=TTS_MODEL, input=[{"type": "user_input", "content": content}],
                              response_format={"type": "audio"}, generation_config={"speech_config": {"speakers": speakers}})
    d = r.model_dump()
    out.write_bytes(base64.b64decode(d["output_audio"]["data"]))
    print(out, f"{wav_duration(out):.1f}s", "tokens", (d.get("usage") or {}).get("total_output_tokens"))


# ---------------------------------------------------------------- B: per turn, spliced
def tts_one(c, text, style, voice, path):
    r = c.interactions.create(
        model=TTS_MODEL,
        input=[{"type": "user_input", "content": [{"type": "text", "text": text,
                "annotations": [{"type": "speech_metadata", "style": style}]}]}],
        response_format={"type": "audio"}, generation_config={"speech_config": [{"voice": voice}]})
    d = r.model_dump()
    path.write_bytes(base64.b64decode(d["output_audio"]["data"]))
    return (d.get("usage") or {}).get("total_output_tokens") or 0


def cmd_gemini_turns(a):
    sc = load(a.script); vo = {k: resolve(v) for k, v in parse_voices(a.voices).items()}
    c = client(); d = OUT / a.name; d.mkdir(parents=True, exist_ok=True)
    tokens = 0
    rej = d / "rejected"
    # --redo: a turn the QA flagged (misread word, wrong delivery) is moved aside and rendered again;
    # with one request per turn, a mistake costs one line, not the whole conversation
    for i in (int(x) for x in a.redo.split(",") if x) if a.redo else []:
        p = d / f"turn_{i:02d}.wav"
        if p.exists():
            rej.mkdir(exist_ok=True); n = len(list(rej.glob(f"turn_{i:02d}_*.wav")))
            p.rename(rej / f"turn_{i:02d}_redo{n}.wav")
    # 1. every turn, without the backchannel markers
    for i, t in enumerate(sc["turns"]):
        p = d / f"turn_{i:02d}.wav"
        for attempt in range(3):
            if p.exists():
                break
            tokens += tts_one(c, BC.sub("", t["text"]), style_for(sc, t), vo[t["speaker"]], p)
            jump = float(np.abs(np.diff(read_wav(p))).max())
            if jump > CLICK and attempt < 2:   # a one-sample jump this big is a digital glitch, not speech
                rej.mkdir(exist_ok=True); n = len(list(rej.glob(f"turn_{i:02d}_*.wav")))
                print(f"turn {i:02d} glitch (sample jump {jump:.2f}), rendering again")
                p.rename(rej / f"turn_{i:02d}_click{n}.wav")
                continue
            print(f"turn {i:02d} {t['speaker']} {wav_duration(p):5.1f}s {BC.sub('', t['text'])[:30]}")
    # 2. backchannel clips, one per (listener, word), a few takes to pick the shortest clean one
    bcs = {}
    for t in sc["turns"]:
        listener = next(k for k in sc["speakers"] if k != t["speaker"])
        for w in BC.findall(t["text"]):
            bcs[(listener, w)] = None
    for (who, w) in bcs:
        best = None
        for k in range(a.bc_takes):
            p = d / f"bc_{who}_{w}_{k}.wav"
            if not p.exists():
                tokens += tts_one(c, w, "在聽對方講話時輕輕附和一聲，很短、很小聲、不打斷對方，嘴巴幾乎沒張開。"
                                  + sc["speakers"][who]["persona"], vo[who], p)
            x = trim(read_wav(p))
            if 0.15 < len(x) / SR < 0.9 and (best is None or len(x) < len(best)):
                best = x
        bcs[(who, w)] = best if best is not None else trim(read_wav(d / f"bc_{who}_{w}_0.wav"))[: int(0.6 * SR)]
    # 3. assemble: loudness per turn, gaps / overlaps, fade the interrupted turn, place backchannels at pauses
    tmp = d / "_tmp.wav"
    clips = [gain_to(trim(read_wav(d / f"turn_{i:02d}.wav")), a.turn_lufs, tmp) for i in range(len(sc["turns"]))]
    starts, t0 = [], 0.4
    for i, (t, x) in enumerate(zip(sc["turns"], clips)):
        if i:
            prev_end = starts[-1] + len(clips[i - 1]) / SR
            t0 = prev_end - t["overlap"] if "overlap" in t else prev_end + t.get("gap", a.gap)
            if "overlap" in t:   # the interrupted speaker trails off 0.25 s after being cut in on
                cut = int((t0 - starts[-1] + 0.25) * SR); fade = int(0.2 * SR)
                y = clips[i - 1][:cut + fade].copy(); y[cut:cut + fade] *= np.linspace(1, 0, len(y[cut:cut + fade]))
                clips[i - 1] = y
        starts.append(t0)
    total = starts[-1] + len(clips[-1]) / SR + 0.6
    mix = np.zeros(int(total * SR) + SR)
    for s, x in zip(starts, clips):
        mix[int(s * SR): int(s * SR) + len(x)] += x
    log = []
    for i, t in enumerate(sc["turns"]):
        parts = BC.split(t["text"])          # text, word, text, word, text ...
        if len(parts) == 1:
            continue
        listener = next(k for k in sc["speakers"] if k != t["speaker"])
        plain_len = len(BC.sub("", t["text"]))
        dur = len(clips[i]) / SR; ps = pauses(clips[i])
        pos = 0
        for j in range(1, len(parts), 2):
            pos += len(parts[j - 1])
            want = dur * pos / plain_len
            # nearest pause; land the 嗯 a little into it so it sits *under* the speaker's breath
            at = min(ps, key=lambda p: abs(p[0] - want))[0] + 0.05 if ps else want
            if ps and abs(at - want) > 1.2:
                at = want
            # a 嗯 is far shorter than LUFS's 400 ms gate, so its loudness meter reads ~silence and
            # gain_to would boost it into clipping; match RMS to the speaker's turn instead
            bc = bcs[(listener, parts[j])]
            bc = bc * (active_rms(clips[i]) / active_rms(bc)) * 10 ** (a.bc_db / 20)
            k0 = int((starts[i] + at) * SR)
            mix[k0:k0 + len(bc)] += bc
            log.append({"turn": i, "listener": listener, "word": parts[j], "at_s": round(starts[i] + at, 2),
                        "wanted_s": round(starts[i] + want, 2), "pauses": [[round(p, 2) for p in q] for q in ps]})
    tmp.unlink(missing_ok=True)
    out = OUT / f"{a.name}.wav"
    write_wav(out, mix[: int(total * SR)] * 0.9)
    (d / "timeline.json").write_text(json.dumps({"starts": [round(s, 2) for s in starts], "backchannels": log},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(out, f"{total:.1f}s", "tokens this run", tokens)


# ---------------------------------------------------------------- C: ElevenLabs text-to-dialogue
EL_TAGS = {"I": "[serious]", "C": "[nervous]"}


def cmd_elevenlabs(a):
    from elevenlabs_tts import call, write_pcm
    sc = load(a.script); vo = parse_voices(a.voices); OUT.mkdir(parents=True, exist_ok=True)
    inputs = []
    for i, t in enumerate(sc["turns"]):
        text = BC.sub("", t["text"])
        tag = t.get("el_tag") or ("[interrupting]" if "overlap" in t else EL_TAGS[t["speaker"]])
        inputs.append({"text": f"{tag} {text}", "voice_id": vo[t["speaker"]]})
    n = sum(len(x["text"]) for x in inputs)
    print("characters", n)
    body = {"inputs": inputs, "model_id": a.model, "language_code": "zh", "seed": a.seed,
            "settings": {"stability": a.stability}}
    pcm = call("/v1/text-to-dialogue?output_format=pcm_24000", body, accept="audio/*")
    out = OUT / f"{a.name}.wav"
    write_pcm(pcm, out)
    (OUT / f"{a.name}.request.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out, f"{wav_duration(out):.1f}s")


# ---------------------------------------------------------------- patch: splice one turn into a render
def cmd_patch(a):
    """Replace [start, end] seconds of src with clip (e.g. the same turn rendered alone by gemini-turns),
    level-matched to the audio it replaces, with `gap` seconds of silence before it."""
    x = read_wav(a.src); y = trim(read_wav(a.clip)); tmp = OUT / "_patch_tmp.wav"
    old = x[int(a.start * SR): int(a.end * SR)]
    write_wav(tmp, old); target = measure_lufs(tmp)
    y = gain_to(y, target, tmp); tmp.unlink(missing_ok=True)
    out = np.concatenate([x[: int(a.start * SR)], np.zeros(int(a.gap * SR)), y, x[int(a.end * SR):]])
    write_wav(a.dst, out)
    print(a.dst, f"replaced {a.end - a.start:.2f}s with {a.gap + len(y) / SR:.2f}s at {target:.1f} LUFS")


# ---------------------------------------------------------------- master
def cmd_master(a):
    Path(a.dst).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.src, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "44100", "-ac", "1", "-b:a", "128k", a.dst], check=True)
    print(a.dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("design")
    for name in ("gemini-multi", "gemini-turns", "elevenlabs"):
        p = sub.add_parser(name)
        p.add_argument("--script", default=str(DEFAULT_SCRIPT))
        p.add_argument("--voices", required=True, help="I=<voice>,C=<voice>")
        p.add_argument("--name", required=True, help="output stem under out/dialogue/")
        if name == "gemini-multi":
            p.add_argument("--no-turn-style", dest="turn_style", action="store_false",
                           help="style = speaker persona only, without the per-turn delivery note")
        if name == "gemini-turns":
            p.add_argument("--gap", type=float, default=0.35)
            p.add_argument("--turn-lufs", type=float, default=-20)
            p.add_argument("--bc-db", type=float, default=-7, help="backchannel level relative to turns")
            p.add_argument("--bc-takes", type=int, default=3)
            p.add_argument("--redo", help="comma-separated turn numbers to render again (see dialogue_qa.py)")
        if name == "elevenlabs":
            p.add_argument("--model", default="eleven_v3")
            p.add_argument("--seed", type=int, default=7)
            p.add_argument("--stability", type=float, default=0.5)
    p = sub.add_parser("master"); p.add_argument("src"); p.add_argument("dst")
    p = sub.add_parser("patch"); p.add_argument("src"); p.add_argument("dst")
    p.add_argument("--start", type=float, required=True); p.add_argument("--end", type=float, required=True)
    p.add_argument("--clip", required=True); p.add_argument("--gap", type=float, default=0.15)
    a = ap.parse_args()
    {"design": cmd_design, "gemini-multi": cmd_gemini_multi, "gemini-turns": cmd_gemini_turns,
     "elevenlabs": cmd_elevenlabs, "patch": cmd_patch, "master": cmd_master}[a.cmd](a)
