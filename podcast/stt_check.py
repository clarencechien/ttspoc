"""Blind intelligibility check: transcribe each segment WITHOUT the script, then diff against the script.

qa_episode.py gives the judge the script, so it "hears" what is written and cannot catch mumbled
words. Here two independent recognisers transcribe blind:
  whisper  faster-whisper large-v3-turbo on CPU (open model, not Gemini)
  gemini   gemini-3.8-flash asked to transcribe only, marking unclear words
A script span that BOTH recognisers miss is flagged as likely unintelligible.
The local recogniser can be Whisper large-v3-turbo or Breeze-ASR-25 (--asr breeze); report keys keep the
"whisper_" prefix for compatibility, and the report's "asr" field says which one was used.

  python podcast/stt_check.py --script podcast/script/ep01_tw.json --segments out/podcast/segments/D1_tw [--out report.json]
"""
import argparse, difflib, json, os, re, sys
from pathlib import Path

FILLERS = set("啊喔哦吼齁欸嗯呃哈啦耶囉嘛呀吧耶誒")
DIGITS = "零一二三四五六七八九"

def num_to_zh(m):
    if len(m.group(0)) == 4:
        return "".join(DIGITS[int(c)] for c in m.group(0))
    n = int(m.group(0))
    if n < 10: return DIGITS[n]
    if n < 100: return (DIGITS[n // 10] if n // 10 > 1 else "") + "十" + (DIGITS[n % 10] if n % 10 else "")
    if n < 1000: return DIGITS[n // 100] + "百" + ("" if n % 100 == 0 else ("零" if n % 100 < 10 else "") + num_to_zh(re.match(r"\d+", str(n % 100))).lstrip("一" if n % 100 >= 10 and n % 100 < 20 else ""))
    return m.group(0)

def norm(s, conv):
    s = conv.convert(s)
    s = re.sub(r"<[^>]+>|［\?］|\[\?\]", "", s)
    s = re.sub(r"\d+", num_to_zh, s)
    s = re.sub(r"[^\w]", "", s).lower()
    return s.replace("醬子", "這樣子").replace("醬", "這樣").replace("兩", "二")

def sounds_same(a, b):
    """True if two spans are pronounced identically INCLUDING tone (e.g. 它/他, 工夫/功夫).
    Tone must count: 季度 ji4du4 heard as 基督 ji1du1 is a real (tone-flattening) error."""
    from pypinyin import pinyin, Style
    tones = lambda w: [x[0] for x in pinyin(w, style=Style.TONE3, neutral_tone_with_five=True)]
    return bool(a) and tones(a) == tones(b)

def real_misses(ms):
    """Drop homophones and dropped/swapped sentence-final particles; keep spans that sound different."""
    out = []
    for x in ms:
        if sounds_same(x["script"], x["heard"]):
            continue
        if all(ch in FILLERS | set("了嗎吧呢") for ch in x["script"]) and all(ch in FILLERS | set("了嗎吧呢") for ch in x["heard"]):
            continue
        out.append(x)
    return out

def cer(ref, hyp):
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(len(ref), 1)

def misses(ref, hyp):
    """Script spans the transcript did not reproduce. Insertions of filler particles are ignored."""
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_opcodes():
        if op == "equal" or op == "insert":
            continue
        heard = hyp[j1:j2]
        if op == "replace" and all(ch in FILLERS for ch in ref[i1:i2]):
            continue
        out.append({"ref_start": i1, "ref_end": i2, "script": ref[i1:i2], "heard": heard,
                    "context": ref[max(0, i1 - 6):i1] + "【" + ref[i1:i2] + "】" + ref[i2:i2 + 6], "hyp_pos": j1})
    return out

ASR_MODELS = {
    # local CTranslate2 int8 conversion of the official MediaTek-Research/Breeze-ASR-25 (Whisper-large-v2 fine-tuned
    # for Taiwanese Mandarin and Mandarin-English code-switching):
    #   ct2-transformers-converter --model MediaTek-Research/Breeze-ASR-25 --output_dir <dir> --quantization int8 \
    #       --copy_files tokenizer.json preprocessor_config.json
    "breeze": os.environ.get("BREEZE_CT2", "/home/user/models/breeze-asr-25-ct2-int8"),
    "whisper": "large-v3-turbo",
}
ASR = "whisper"

def whisper_transcribe(paths):
    from faster_whisper import WhisperModel
    m = WhisperModel(ASR_MODELS[ASR], device="cpu", compute_type="int8")
    res = {}
    for p in paths:
        import wave
        with wave.open(str(p)) as w:
            dur = w.getnframes() / w.getframerate()
        kw = dict(language="zh", beam_size=5, vad_filter=True)
        if ASR == "whisper":   # Breeze is used as published, without a prompt
            kw["initial_prompt"] = "以下是台灣華語的科技 podcast，繁體中文。"
        segs = list(m.transcribe(str(p), **kw)[0])
        if segs and segs[-1].end > dur + 1.0:
            # Whisper hallucinated past the end of the audio and kept feeding on its own text; retry without that context
            print(f"  whisper {p.stem}: timestamps run to {segs[-1].end:.0f}s on {dur:.0f}s of audio, retrying")
            segs = list(m.transcribe(str(p), condition_on_previous_text=False, temperature=0.0, **kw)[0])
        res[p.stem] = {"text": "".join(s.text for s in segs), "segments": [(round(s.start, 2), s.text) for s in segs]}
        print(f"  {ASR} {p.stem}: {res[p.stem]['text'][:40]}…")
    return res

GEMINI_PROMPT = ("請逐字聽寫這段台灣華語音檔。只輸出你聽到的文字，用繁體中文，數字照念出來的寫成中文。"
                 "聽不清楚或不確定的字，用［?］代替，不要猜。不要加任何說明。")

def gemini_transcribe(paths):
    from google import genai
    from google.genai import types
    c = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])
    res = {}
    for p in paths:
        r = c.models.generate_content(model="gemini-3.8-flash",
              contents=[types.Part.from_bytes(data=p.read_bytes(), mime_type="audio/wav"), GEMINI_PROMPT],
              config=types.GenerateContentConfig(temperature=0))
        res[p.stem] = {"text": r.text.strip(), "unclear_marks": r.text.count("［?］") + r.text.count("[?]")}
        print(f"  gemini  {p.stem}: {res[p.stem]['text'][:40]}…")
    return res

def overlaps(a, b):
    return a["ref_start"] < b["ref_end"] and b["ref_start"] < a["ref_end"] or (a["ref_start"] == b["ref_start"])

def main(a):
    import opencc, wave
    conv = opencc.OpenCC("s2twp")
    sc = json.loads(Path(a.script).read_text(encoding="utf-8")); d = Path(a.segments)
    paths = [d / f"{s['id']}.wav" for s in sc["segments"]]
    if a.reuse and Path(a.reuse).exists():
        old = {r["id"]: r for r in json.loads(Path(a.reuse).read_text(encoding="utf-8"))["segments"]}
        W = {k: {"text": v["whisper_text"], "segments": [tuple(x) for x in v["whisper_segments"]]} for k, v in old.items()}
        G = {k: {"text": v["gemini_text"], "unclear_marks": v["gemini_unclear_marks"]} for k, v in old.items()}
        print("reusing transcripts from", a.reuse)
    else:
        print("transcribing with whisper…"); W = whisper_transcribe(paths)
        print("transcribing with gemini…"); G = gemini_transcribe(paths)
    report = {"script": a.script, "asr": ASR, "asr_model": ASR_MODELS[ASR],
              "method": f"blind STT ({ASR} + Gemini 3.8 Flash), tone-aware pinyin filter drops exact homophones", "segments": []}
    t = 3.6   # intro sting 3.2 s + lead 0.4 s; 0.6 s gaps between segments (make_podcast.cmd_master)
    for s, p in zip(sc["segments"], paths):
        ref = norm(s["text"], conv); wh, ge = norm(W[p.stem]["text"], conv), norm(G[p.stem]["text"], conv)
        mw, mg = real_misses(misses(ref, wh)), real_misses(misses(ref, ge))
        flagged = []
        for x in mw + [y for y in mg if not any(overlaps(y, z) for z in mw)]:
            in_w = any(overlaps(x, z) for z in mw); in_g = any(overlaps(x, z) for z in mg)
            pos = 0; when = 0.0
            if in_w:
                for start, txt in W[p.stem]["segments"]:
                    if pos + len(norm(txt, conv)) > x["hyp_pos"]:
                        when = start; break
                    pos += len(norm(txt, conv))
            flagged.append({**x, "by": "both" if in_w and in_g else ("whisper" if in_w else "gemini"),
                            "whisper_heard": next((z["heard"] for z in mw if overlaps(x, z)), "—"),
                            "gemini_heard": next((z["heard"] for z in mg if overlaps(x, z)), "—"),
                            "episode_time": f"{int((t + when) // 60)}:{int((t + when) % 60):02d}" if in_w else "?"})
        with wave.open(str(p)) as w:
            dur = w.getnframes() / w.getframerate()
        report["segments"].append({"id": s["id"], "cer_whisper": round(cer(ref, wh), 3), "cer_gemini": round(cer(ref, ge), 3),
                                   "gemini_unclear_marks": G[p.stem]["unclear_marks"], "flagged": flagged,
                                   "whisper_text": W[p.stem]["text"], "whisper_segments": W[p.stem]["segments"], "gemini_text": G[p.stem]["text"]})
        t += dur + 0.6
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'段落':16s} {ASR + ' CER':>11s} {'Gemini CER':>10s} {'發音不同':>8s} {'兩邊都錯':>8s}")
    for r in report["segments"]:
        print(f"{r['id']:16s} {r['cer_whisper']:11.3f} {r['cer_gemini']:10.3f} {len(r['flagged']):8d} {sum(1 for x in r['flagged'] if x['by']=='both'):8d}")
    print("\n聽起來跟稿子不同的地方（同音字已排除；時間是整集裡的位置）：")
    for r in report["segments"]:
        for x in r["flagged"]:
            print(f"  {x['episode_time']:>5s} {r['id']:15s} [{x['by']:7s}] 稿子「{x['script']}」 {ASR}「{x['whisper_heard']}」 Gemini「{x['gemini_heard']}」  …{x['context']}…")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--script", required=True); ap.add_argument("--segments", required=True)
    ap.add_argument("--out"); ap.add_argument("--reuse", help="report JSON from an earlier run; skips transcription")
    ap.add_argument("--asr", choices=list(ASR_MODELS), default="whisper", help="local recogniser: whisper large-v3-turbo or Breeze-ASR-25")
    a = ap.parse_args(); ASR = a.asr
    main(a)
