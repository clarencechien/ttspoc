"""Discriminative voice comparison: (1) objective pitch / brightness, (2) blind comparative ranking.

The per-clip judge in make_podcast.py gives almost every voice 25/25, so it cannot pick a winner.
Here all clips go into ONE judge request under shuffled letter labels and must be ranked against
each other; plus median F0 (autocorrelation) and spectral centroid as objective 'low / dark' proxies.

  python podcast/compare_voices.py out/podcast/audition/*.wav
"""
import json, os, random, sys, wave
from pathlib import Path
import numpy as np
from google import genai
from google.genai import types

def load(path):
    with wave.open(str(path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        return x, w.getframerate()

def f0_track(x, sr, fmin=60, fmax=300, win=0.04, hop=0.01):
    n, h = int(sr * win), int(sr * hop); out = []
    lo, hi = int(sr / fmax), int(sr / fmin)
    for i in range(0, len(x) - n, h):
        fr = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt((fr ** 2).mean()) < 0.02:   # skip silence / breaths
            continue
        ac = np.correlate(fr, fr, "full")[n - 1:]
        if ac[0] <= 0: continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] / ac[0] > 0.45:              # voiced frames only
            out.append(sr / lag)
    return np.array(out)

def centroid(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float((spec * f).sum() / spec.sum())

RANK_PROMPT = """你是台灣 podcast 製作人，要幫「深夜科技 podcast」挑男主持人。下面有 {n} 段音檔，標籤依序是 {labels}，唸的是同一段稿。
目標：台灣國語口音、低沉有磁性（像深夜電台）、慵懶放鬆像跟朋友聊天、會自嘲、英文技術名詞自然。
請互相比較，不可以並列，只輸出 JSON：
{"ranking": ["最適合的標籤", "...", "最不適合的標籤"],
 "per_clip": {"A": {"taiwan_accent": "一句話", "magnetic_low": "一句話", "weakness": "最明顯的缺點"}, "...": {}},
 "winner_reason": "為什麼第一名勝出"}"""

def main(files):
    rows = []
    for f in files:
        x, sr = load(f); f0 = f0_track(x, sr)
        rows.append({"file": Path(f).name, "f0_median_hz": round(float(np.median(f0)), 1) if len(f0) else None,
                     "f0_p10_p90": [round(float(np.percentile(f0, 10)), 1), round(float(np.percentile(f0, 90)), 1)] if len(f0) else None,
                     "centroid_hz": round(centroid(x, sr)), "duration_s": round(len(x) / sr, 1)})
    print(f"{'file':28s} {'F0 med':>7s} {'F0 p10-p90':>14s} {'centroid':>9s} {'dur':>5s}")
    for r in sorted(rows, key=lambda r: r["f0_median_hz"] or 999):
        print(f"{r['file']:28s} {r['f0_median_hz']:7.1f} {str(r['f0_p10_p90']):>14s} {r['centroid_hz']:9d} {r['duration_s']:5.1f}")
    c = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])
    rankings = []
    for trial in range(3):  # three shuffles to wash out position bias
        order = files[:]; random.Random(trial).shuffle(order)
        labels = [chr(65 + i) for i in range(len(order))]
        parts = []
        for lab, f in zip(labels, order):
            parts += [f"音檔 {lab}：", types.Part.from_bytes(data=Path(f).read_bytes(), mime_type="audio/wav")]
        parts.append(RANK_PROMPT.replace("{n}", str(len(order))).replace("{labels}", "、".join(labels)))
        r = c.models.generate_content(model="gemini-3.8-flash", contents=parts,
                                      config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
        j = json.loads(r.text); m = dict(zip(labels, [Path(f).name for f in order]))
        ranked = [m[l] for l in j["ranking"] if l in m]
        rankings.append({"ranking": ranked, "winner_reason": j.get("winner_reason"),
                         "per_clip": {m.get(k, k): v for k, v in (j.get("per_clip") or {}).items()}})
        print(f"\ntrial {trial}: " + " > ".join(x.split('.')[0] for x in ranked) + f"\n  winner: {j.get('winner_reason')}")
    score = {r["file"]: 0 for r in rows}
    for t in rankings:
        for pos, name in enumerate(t["ranking"]):
            score[name] = score.get(name, 0) + (len(t["ranking"]) - pos)
    print("\nBorda total over 3 shuffles:")
    for name, s in sorted(score.items(), key=lambda kv: -kv[1]):
        print(f"  {name:28s} {s}")
    out = Path(files[0]).parent.parent / "voice_comparison.json"
    out.write_text(json.dumps({"objective": rows, "rankings": rankings, "borda": score}, ensure_ascii=False, indent=1))
    print("->", out)

if __name__ == "__main__":
    main(sys.argv[1:])
