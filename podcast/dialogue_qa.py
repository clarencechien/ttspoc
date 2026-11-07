"""QA for two-person dialogue renders: Breeze-ASR-25 blind transcript + who-said-what check.

  python podcast/dialogue_qa.py out/dialogue/A.wav out/dialogue/B.wav ... [--script ...]

For each file:
  - CER of the Breeze transcript against the script (backchannel markers removed) and the misses that
    do not sound the same with tone (stt_check.real_misses).
  - Breeze word timestamps place each script turn in time; the median F0 of each turn must sit on its own
    speaker's side of the midpoint between the two speakers' medians (female interviewer / male candidate).
    A turn on the wrong side is a wrong-voice line (a multi-speaker request can give a line to the other voice).
"""
import argparse, difflib, json, re, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stt_check
from stt_check import norm, cer, misses, real_misses

ROOT = Path(__file__).resolve().parent.parent
BC = re.compile(r"\[\[(.+?)\]\]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--script", default=str(ROOT / "podcast/dialogue/interview_claude_sessions.json"))
    ap.add_argument("--out", default=str(ROOT / "out/dialogue/qa.json"))
    a = ap.parse_args()
    from opencc import OpenCC
    conv = OpenCC("s2twp")
    sc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    turns = [norm(BC.sub("", t["text"]), conv) for t in sc["turns"]]
    owner = []                       # char index in the joined reference -> turn index
    for i, t in enumerate(turns):
        owner += [i] * len(t)
    ref = "".join(turns)

    from faster_whisper import WhisperModel
    sys.path.insert(0, str(ROOT / "podcast"))
    from compare_voices import f0_track
    import wave
    model = WhisperModel(stt_check.ASR_MODELS["breeze"], device="cpu", compute_type="int8")

    report = {}
    for f in a.files:
        stem = Path(f).stem
        segs = list(model.transcribe(f, language="zh", beam_size=5, vad_filter=True, word_timestamps=True)[0])
        text = "".join(s.text for s in segs)
        hyp_full = norm(text, conv)
        ms = real_misses(misses(ref, hyp_full))
        # every normalised hypothesis char gets the time of the word it came from
        chars = []
        for s in segs:
            for w in s.words:
                for ch in norm(w.word, conv):
                    chars.append((ch, w.start, w.end))
        hyp = "".join(c for c, _, _ in chars)
        spans = {}
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_opcodes():
            if op != "equal":
                continue
            for k in range(i2 - i1):
                t = owner[i1 + k]; _, s0, s1 = chars[j1 + k]
                lo, hi = spans.get(t, (s0, s1)); spans[t] = (min(lo, s0), max(hi, s1))
        with wave.open(f) as w:
            sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        rows = []
        for t, (s0, s1) in sorted(spans.items()):
            seg = x[int((s0 + 0.1) * sr): int((s1 - 0.1) * sr)]     # stay clear of overlapping turn edges
            f0 = f0_track(seg, sr, fmin=60, fmax=400) if len(seg) > sr * 0.3 else np.array([])
            rows.append({"turn": t, "speaker": sc["turns"][t]["speaker"], "start": round(s0, 2), "end": round(s1, 2),
                         "f0": round(float(np.median(f0)), 1) if len(f0) > 10 else None})
        med = {k: float(np.median([r["f0"] for r in rows if r["speaker"] == k and r["f0"]])) for k in sc["speakers"]}
        cut = (med["I"] + med["C"]) / 2
        hi_spk = max(med, key=med.get)
        same_gender = len({p.get("gender") for p in sc["speakers"].values()}) == 1
        # pitch only separates a woman from a man; with two men (or two women) the check means nothing
        wrong = [] if same_gender else [r for r in rows if r["f0"] and ((r["f0"] > cut) != (r["speaker"] == hi_spk))]
        missing = [i for i in range(len(turns)) if i not in spans]
        miss_turns = sorted({owner[min(m["ref_start"], len(owner) - 1)] for m in ms})
        report[stem] = {"cer": round(cer(ref, hyp_full), 4),
                        "real_misses": [f"t{owner[min(m['ref_start'], len(owner) - 1)]:02d} " + m["context"] + " → " + m["heard"] for m in ms],
                        "turns_with_misses": miss_turns,
                        "f0_median": {k: round(v, 1) for k, v in med.items()}, "turns": rows,
                        "wrong_voice_turns": wrong, "turns_not_found": missing, "transcript": text}
        print(f"\n{stem}: CER {cer(ref, hyp_full):.1%}  misses {len(ms)}  F0 I={med['I']:.0f} C={med['C']:.0f} Hz  "
              f"wrong-voice turns {len(wrong)}  turns not found {missing}")
        print("   turns with misses (redo candidates for gemini-turns --redo):", ",".join(map(str, miss_turns)))
        for m in report[stem]["real_misses"]:
            print("   miss:", m)
        for r in wrong:
            print("   wrong voice:", r, BC.sub("", sc["turns"][r["turn"]]["text"])[:24])
    Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
