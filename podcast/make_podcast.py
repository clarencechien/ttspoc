"""Podcast POC pipeline on Gemini 3.8 TTS.

  python podcast/make_podcast.py design                 # create designed voices D1/D2 -> out/podcast/voices.json
  python podcast/make_podcast.py audition               # same audition line in every candidate voice
  python podcast/make_podcast.py judge out/podcast/audition/*.wav
  python podcast/make_podcast.py episode --voice D1     # all segments, verified, retried
  python podcast/make_podcast.py master --voice D1      # stings + silence + loudnorm -> mp3

Text is spoken verbatim by 3.8 TTS; delivery goes in speech_metadata.style.
Every segment is checked against the duration the text implies, because 3.8 TTS can
stop early without returning an error (see experiments/pilot/latency_pilot.jsonl).
"""
import argparse, base64, json, math, os, re, shutil, struct, subprocess, sys, time, wave
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "podcast"
SCRIPT = ROOT / "podcast" / "script" / "ep01.json"
TTS_MODEL = "gemini-3.8-flash-tts"
JUDGE_MODEL = "gemini-3.8-flash"
SR = 24000
CHARS_PER_SEC = 4.5
OK_RATIO = (0.6, 1.6)

DESIGNS = {
    "D1": ("磁性深夜",
           "三十五歲左右的台灣男生，講標準台灣國語，聲音低沉、有磁性，帶一點點沙啞和氣音，"
           "慵懶放鬆，像深夜電台主持人在跟朋友聊天，偶爾自嘲、帶點痞痞的幽默。"
           "沒有中國大陸的捲舌腔和兒化音。"),
    "D2": ("工程師學長",
           "三十歲左右的台灣男工程師，講標準台灣國語，聲音低沉、溫暖、有磁性，咬字清楚，"
           "講到技術時自信又帶點興奮，像科技 podcast 主持人，中英夾雜很自然，英文技術名詞發音標準。"
           "沒有中國大陸的捲舌腔和兒化音。"),
}
STUDIO = {"S1": "Algieba", "S2": "Charon", "S3": "Enceladus", "S4": "Umbriel"}


def client():
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])


def load_script(path=None):
    return json.loads(Path(path or SCRIPT).read_text(encoding="utf-8"))


def seg_dir(a):
    """Output folder for one voice + script version, e.g. segments/D1 or segments/D1_tw."""
    return OUT / "segments" / (f"{a.voice}_{a.tag}" if getattr(a, "tag", "") else a.voice)


def long_pauses(path, min_len=0.6):
    """Count pauses of at least min_len seconds (ignoring leading and trailing silence)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise=-35dB:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r)]
    dur = wav_duration(path)
    return sum(1 for t in starts if 0.2 < t < dur - 0.8)


def spoken_chars(text):
    return len(re.sub(r"<[^>]+>|[\s，。、！？「」〈〉：；.,!?:;]", "", text))


def registry():
    p = OUT / "voices.json"
    return json.loads(p.read_text()) if p.exists() else {}


def voice_id(key):
    reg = registry()
    if key in reg:
        return reg[key]["id"]
    if key in STUDIO:
        return STUDIO[key]
    return key  # raw voice name or voice_... id


def wav_duration(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def tts(c, text, style, voice, path):
    t0 = time.perf_counter()
    r = c.interactions.create(
        model=TTS_MODEL,
        input=[{"type": "user_input", "content": [{"type": "text", "text": text,
                "annotations": [{"type": "speech_metadata", "style": style}]}]}],
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice}]})
    d = r.model_dump()
    path.write_bytes(base64.b64decode(d["output_audio"]["data"]))
    return time.perf_counter() - t0, (d.get("usage") or {}).get("total_output_tokens")


def cmd_design(a):
    c = client(); OUT.mkdir(parents=True, exist_ok=True)
    reg = registry()
    for key, (name, prompt) in DESIGNS.items():
        if key in reg:
            print("exists", key, reg[key]["id"]); continue
        v = c.voices.create(store=True, voice={
            "model": TTS_MODEL, "type": "prompted", "display_name": f"podcast-{key}-{name}",
            "gender": "male", "language_code": "zh-TW", "prompted": {"input": prompt}}).model_dump()
        (OUT / f"design_sample_{key}.wav").write_bytes(base64.b64decode(v["sample_audio"]["data"]))
        reg[key] = {"id": v["id"], "name": name, "prompt": prompt, "expire_time": str(v.get("expire_time"))}
        (OUT / "voices.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1))
        print("created", key, v["id"])


def cmd_audition(a):
    c = client(); sc = load_script(); d = OUT / "audition"; d.mkdir(parents=True, exist_ok=True)
    keys = a.voices.split(",") if a.voices else list(DESIGNS) + list(STUDIO)
    for k in keys:
        p = d / f"{k}_{STUDIO.get(k, registry().get(k, {}).get('name', k))}.wav"
        wall, tok = tts(c, sc["audition_text"], sc["base_style"], voice_id(k), p)
        print(f"{k:4s} {p.name:28s} wall={wall:5.1f}s audio={wav_duration(p):5.1f}s tokens={tok}")


JUDGE_PROMPT = """你是台灣 podcast 製作人，正在幫一個「深夜科技 podcast」挑男主持人的聲音。
目標聲音：台灣國語口音、低沉有磁性、慵懶放鬆、像跟朋友聊天、會自嘲，英文技術名詞唸得自然。
請聽音檔並對照原文，只輸出 JSON：
{"transcript": "逐字稿", "taiwan_accent_1to5": n, "magnetic_low_1to5": n, "relaxed_conversational_1to5": n,
 "english_terms_1to5": n, "naturalness_1to5": n, "mispronunciations": ["詞：聽到的唸法"],
 "tags_read_aloud": true或false, "truncated": true或false, "voice_drift": true或false, "verdict": "一句話評語"}
原文：{text}"""


def judge(c, path, text):
    r = c.models.generate_content(
        model=JUDGE_MODEL,
        contents=[types.Part.from_bytes(data=Path(path).read_bytes(), mime_type="audio/wav"),
                  JUDGE_PROMPT.replace("{text}", text)],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
    try:
        return json.loads(r.text)
    except Exception:
        return {"raw": r.text}


def cmd_judge(a):
    c = client(); sc = load_script(); rows = []
    for f in a.files:
        text = a.text or sc["audition_text"]
        j = judge(c, f, text)
        keys = ["taiwan_accent_1to5", "magnetic_low_1to5", "relaxed_conversational_1to5", "english_terms_1to5", "naturalness_1to5"]
        score = sum(j.get(k, 0) or 0 for k in keys)
        rows.append({"file": Path(f).name, "score": score, **j})
        print(f"{Path(f).name:30s} total={score:2d}/25 " + " ".join(f"{k.split('_')[0]}={j.get(k)}" for k in keys) + f" | {j.get('verdict')}")
    out = Path(a.out) if a.out else OUT / "audition_judged.json"
    out.write_text(json.dumps(sorted(rows, key=lambda r: -r["score"]), ensure_ascii=False, indent=1))


def cmd_episode(a):
    c = client(); sc = load_script(a.script); d = seg_dir(a); d.mkdir(parents=True, exist_ok=True)
    vid = voice_id(a.voice); log = []
    log_path = d / "log.json"
    old = {r["id"]: r for r in json.loads(log_path.read_text())} if log_path.exists() else {}
    only = set(a.only.split(",")) if a.only else None
    for s in sc["segments"]:
        if only and s["id"] not in only:
            if s["id"] in old: log.append(old[s["id"]])
            continue
        if only: a.force = True
        p = d / f"{s['id']}.wav"
        expected = spoken_chars(s["text"]) / CHARS_PER_SEC
        base = sc.get(f"base_style_{a.style}", sc["base_style"]) if a.style != "v1" else sc["base_style"]
        style = f"{base}。這一段：{s['mood']}"
        takes = []
        for k in range(a.takes):
            tp = p if a.takes == 1 else d / f"{s['id']}.take{k}.wav"
            for attempt in range(1, a.retries + 2):
                if tp.exists() and not a.force and attempt == 1:
                    wall, tok = 0.0, None
                else:
                    wall, tok = tts(c, s["text"], style, vid, tp)
                dur = wav_duration(tp); ratio = dur / expected
                ok = OK_RATIO[0] <= ratio <= OK_RATIO[1]
                lp = long_pauses(tp)
                print(f"{s['id']:16s} take{k} try{attempt} wall={wall:5.1f}s audio={dur:5.1f}s expected~{expected:5.1f}s ratio={ratio:4.2f} pauses>=0.6s={lp} {'OK' if ok else 'RETRY'}")
                if ok:
                    break
                a.force = True  # cached file failed the check; regenerate
            a.force = a.force and bool(only)
            takes.append({"path": tp, "ok": ok, "dur": dur, "ratio": ratio, "pauses": lp, "wall": wall, "tok": tok, "attempt": attempt})
        # pick: passes the duration check, then fewest long pauses per minute, then shorter
        best = min(takes, key=lambda t: (not t["ok"], t["pauses"] / max(t["dur"], 1) * 60, t["dur"]))
        if best["path"] != p:
            shutil.copyfile(best["path"], p)
        dur, ratio, ok, wall, tok, attempt = best["dur"], best["ratio"], best["ok"], best["wall"], best["tok"], best["attempt"]
        log.append({"id": s["id"], "attempts": attempt, "audio_s": round(dur, 2), "expected_s": round(expected, 1),
                    "ratio": round(ratio, 2), "ok": ok, "wall_s": round(wall, 1), "tokens": tok,
                    "takes": [{"file": t["path"].name, "audio_s": round(t["dur"], 1), "pauses_ge_0_6s": t["pauses"], "ok": t["ok"]} for t in takes],
                    "chosen": best["path"].name})
        a.force = False
    (d / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
    bad = [r["id"] for r in log if not r["ok"]]
    print("all segments OK" if not bad else f"FAILED after retries: {bad}")


def synth_sting(path, seconds=3.2, rising=True):
    """Short synth 'boot' sting: arpeggiated sine pluck over a low pad, generated in code (no samples)."""
    notes = [220.0, 277.18, 329.63, 440.0] if rising else [440.0, 329.63, 277.18, 220.0]
    n = int(SR * seconds); frames = bytearray()
    for i in range(n):
        t = i / SR
        pad = 0.10 * math.sin(2 * math.pi * 110 * t) * min(1, t / 0.4) * max(0.0, 1 - t / seconds)
        pad += 0.05 * math.sin(2 * math.pi * 164.81 * t) * min(1, t / 0.6) * max(0.0, 1 - t / seconds)
        pl = 0.0
        for k, f in enumerate(notes):
            t0 = 0.18 * k
            if t >= t0:
                dt = t - t0
                pl += 0.22 * math.exp(-4.5 * dt) * (math.sin(2 * math.pi * f * dt) + 0.3 * math.sin(4 * math.pi * f * dt))
        v = max(-1.0, min(1.0, pad + pl))
        frames += struct.pack("<h", int(v * 32767 * 0.8))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(frames))


def silence(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(b"\x00\x00" * int(SR * seconds))


BANDS = [100 * 2 ** (k / 3) for k in range(0, 21)]   # 1/3-octave band edges, 100 Hz to ~10 kHz


def band_spectrum(path):
    """Long-term average spectrum in 1/3-octave bands (dB, mean-removed), voiced/active frames only."""
    import numpy as np
    with wave.open(str(path)) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = 4096; win = np.hanning(n); acc = np.zeros(n // 2 + 1); k = 0
    for i in range(0, len(x) - n, n // 2):
        fr = x[i:i + n]
        if np.sqrt(np.mean(fr ** 2)) < 0.01:
            continue
        acc += np.abs(np.fft.rfft(fr * win)) ** 2; k += 1
    f = np.fft.rfftfreq(n, 1 / sr)
    db = np.array([10 * np.log10(acc[(f >= lo) & (f < hi)].mean() / max(k, 1) + 1e-12) for lo, hi in zip(BANDS[:-1], BANDS[1:])])
    return db - db.mean()


def apply_band_eq(src, dst, gains_db):
    """Linear-phase EQ through the 1/3-octave band centres (ffmpeg firequalizer)."""
    centres = [(lo * hi) ** 0.5 for lo, hi in zip(BANDS[:-1], BANDS[1:])]
    entries = ";".join(f"entry({c:.0f},{g:.2f})" for c, g in zip(centres, gains_db))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"firequalizer=gain_entry='{entries}':zero_phase=on",
                    "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)


def measure_lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", r)[-1])


def cmd_master(a):
    sc = load_script(a.script); d = seg_dir(a); m = OUT / "master"; m.mkdir(parents=True, exist_ok=True)
    synth_sting(m / "intro.wav", rising=True); synth_sting(m / "outro.wav", rising=False)
    silence(m / "gap.wav", 0.6); silence(m / "lead.wav", 0.4)
    seq = [m / "intro.wav", m / "lead.wav"]
    name = f"{a.voice}_{a.tag}" if a.tag else a.voice
    norm_dir = m / f"norm_{name}"; norm_dir.mkdir(exist_ok=True); levels = []
    for i, s in enumerate(sc["segments"]):
        src = d / f"{s['id']}.wav"
        if a.seg_lufs == a.seg_lufs:   # NaN disables per-segment normalization
            # Per-segment loudness: segments come from separate TTS requests and differ by several dB; the
            # whole-episode loudnorm below cannot fix that, so bring each one to the same level first.
            before = measure_lufs(src); out = norm_dir / src.name
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"volume={a.seg_lufs - before:.2f}dB",
                            "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(out)], check=True)
            levels.append({"id": s["id"], "lufs_before": round(before, 1), "gain_db": round(a.seg_lufs - before, 1), "lufs_after": round(measure_lufs(out), 1)})
            src = out
        seq.append(src)
    if a.match_eq and a.seg_lufs == a.seg_lufs:
        # Tonal matching: pull every segment's long-term spectrum toward the episode median, then re-level.
        import numpy as np
        seg_files = [x for x in seq if x.parent == norm_dir]
        specs = np.array([band_spectrum(x) for x in seg_files]); target = np.median(specs, axis=0); eq_log = []
        for x, sp in zip(seg_files, specs):
            g = np.clip((target - sp) * a.match_strength, -a.match_max_db, a.match_max_db)
            g = np.convolve(np.pad(g, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid")     # smooth across neighbouring bands
            tmp = x.with_suffix(".eq.wav"); apply_band_eq(x, tmp, g)
            lv = measure_lufs(tmp)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-af", f"volume={a.seg_lufs - lv:.2f}dB",
                            "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(x)], check=True)
            tmp.unlink()
            eq_log.append({"id": x.stem, "gains_db": [round(float(v), 2) for v in g],
                           "deviation_before_db": round(float(np.sqrt(np.mean((sp - target) ** 2))), 2),
                           "deviation_after_db": round(float(np.sqrt(np.mean((band_spectrum(x) - target) ** 2))), 2)})
        (norm_dir / "match_eq.json").write_text(json.dumps(eq_log, ensure_ascii=False, indent=1))
        print("tonal match, spectral deviation dB:", " ".join(f"{e['deviation_before_db']}->{e['deviation_after_db']}" for e in eq_log))
        if i < len(sc["segments"]) - 1:
            seq.append(m / "gap.wav")
    seq += [m / "lead.wav", m / "outro.wav"]
    if levels:
        (norm_dir / "levels.json").write_text(json.dumps(levels, ensure_ascii=False, indent=1))
        print("segment loudness before:", " ".join(f"{x['lufs_before']}" for x in levels), f"-> all {a.seg_lufs} LUFS")
    lst = m / f"concat_{name}.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in seq))
    raw = m / f"ep01_{name}_raw.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)], check=True)
    mp3 = OUT / f"ep01_{name}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                    "-af", "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200,loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k",
                    "-metadata", f"title={sc['episode']}", "-metadata", f"artist={sc['show']}", str(mp3)], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                               capture_output=True, text=True).stdout)
    print(f"{mp3}  {dur/60:.1f} min  {mp3.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("design")
    p = sub.add_parser("audition"); p.add_argument("--voices", default="")
    p = sub.add_parser("judge"); p.add_argument("files", nargs="+"); p.add_argument("--text"); p.add_argument("--out")
    p = sub.add_parser("episode"); p.add_argument("--voice", required=True); p.add_argument("--retries", type=int, default=2); p.add_argument("--force", action="store_true"); p.add_argument("--only", default="", help="comma-separated segment ids to regenerate"); p.add_argument("--script", default=None, help="script JSON, default podcast/script/ep01.json"); p.add_argument("--tag", default="", help="suffix for the segments folder and output, e.g. tw"); p.add_argument("--takes", type=int, default=1, help="takes per segment; keeps the one with fewest long pauses"); p.add_argument("--style", choices=["v1", "v2", "v3", "v4", "v5"], default="v1", help="v2 = confident and rhythmic but drifts toward a broadcast accent; v3 = rhythmic and Taiwanese-leaning; v4 = v3 plus explicit Taiwan Mandarin phonetic traits and an amateur feel; v5 = v4 plus clear tones (in ep01_tw.json)")
    p = sub.add_parser("master"); p.add_argument("--voice", required=True); p.add_argument("--script", default=None); p.add_argument("--tag", default="")
    p.add_argument("--seg-lufs", type=float, default=-20.0, help="bring every segment to this loudness before joining; pass nan to skip")
    p.add_argument("--match-eq", action="store_true", help="tonal matching: EQ each segment toward the episode's median spectrum")
    p.add_argument("--match-strength", type=float, default=0.8); p.add_argument("--match-max-db", type=float, default=6.0)
    a = ap.parse_args()
    {"design": cmd_design, "audition": cmd_audition, "judge": cmd_judge, "episode": cmd_episode, "master": cmd_master}[a.cmd](a)
