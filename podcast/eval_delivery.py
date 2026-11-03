"""Compare delivery of several takes of the SAME text: objective measures + blind comparative ranking.

  python podcast/eval_delivery.py --text-file path.txt clip1.wav clip2.wav ... [--out results.json]

Objective: median F0 (lower = deeper), speaking rate (spoken chars / sec), pauses >= 0.35 s found by
ffmpeg silencedetect (count, longest, per 100 chars), spectral centroid.
Blind ranking: all clips in one judge request under shuffled letters, 3 shuffles, Borda count, on the
criteria the host brief cares about: confident not timid, rhythm, natural pause placement, magnetic depth.
"""
import argparse, json, os, random, re, subprocess, sys
from pathlib import Path
import numpy as np
from google import genai
from google.genai import types
sys.path.insert(0, str(Path(__file__).parent))
from compare_voices import load, f0_track, centroid

RANK = """你是台灣 podcast 製作人，要挑「深夜科技 podcast」男主持人這一段的最佳版本。{n} 段音檔（標籤 {labels}）念的是同一段稿。
評分重點：
1. 自信、篤定，不畏縮、不遲疑
2. 有節奏感、有起伏，不平板
3. 停頓位置自然，不會在句子中間或奇怪的地方拖慢
4. 聲音低沉、有磁性、胸腔共鳴飽滿
5. 台灣口音自然
請互相比較，不可並列，只輸出 JSON：
{"ranking": ["最好的標籤", "...", "最差的標籤"],
 "per_clip": {"A": {"confidence": "一句話", "rhythm_pauses": "一句話，指出奇怪停頓的位置", "magnetic": "一句話"}},
 "winner_reason": "一句話"}"""

def pauses(path, noise="-35dB", d=0.35):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    durs = [float(x) for x in re.findall(r"silence_duration: ([0-9.]+)", r)]
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r)]
    return [(s, d_) for s, d_ in zip(starts, durs) if s > 0.2]   # ignore leading silence

def main(a):
    text = Path(a.text_file).read_text(encoding="utf-8") if a.text_file else ""
    spoken = len(re.sub(r"<[^>]+>|[\s，。、！？「」〈〉：；…\.,!?:;]", "", text)) if text else None
    rows = []
    for f in a.files:
        x, sr = load(f); f0 = f0_track(x, sr); dur = len(x) / sr
        ps = [p for p in pauses(f) if p[0] < dur - 0.5]   # drop trailing silence
        rows.append({"file": Path(f).name, "duration_s": round(dur, 1),
                     "f0_median_hz": round(float(np.median(f0)), 1), "centroid_hz": round(centroid(x, sr)),
                     "chars_per_sec": round(spoken / dur, 2) if spoken else None,
                     "pauses": len(ps), "longest_pause_s": round(max([p[1] for p in ps], default=0), 2),
                     "pauses_over_0_8s": sum(1 for p in ps if p[1] >= 0.8),
                     "pauses_per_100_chars": round(len(ps) / spoken * 100, 1) if spoken else None})
    print(f"{'clip':30s} {'dur':>5s} {'F0':>6s} {'字/秒':>6s} {'停頓':>4s} {'>0.8s':>5s} {'最長':>5s} {'重心':>6s}")
    for r in rows:
        print(f"{r['file']:30s} {r['duration_s']:5.1f} {r['f0_median_hz']:6.1f} {r['chars_per_sec'] or 0:6.2f} {r['pauses']:4d} {r['pauses_over_0_8s']:5d} {r['longest_pause_s']:5.2f} {r['centroid_hz']:6d}")
    c = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])
    trials = []; borda = {r["file"]: 0 for r in rows}
    for t in range(a.shuffles):
        order = a.files[:]; random.Random(100 + t).shuffle(order)
        labels = [chr(65 + i) for i in range(len(order))]
        parts = []
        for lab, f in zip(labels, order):
            parts += [f"音檔 {lab}：", types.Part.from_bytes(data=Path(f).read_bytes(), mime_type="audio/wav")]
        parts.append(RANK.replace("{n}", str(len(order))).replace("{labels}", "、".join(labels)))
        j = json.loads(c.models.generate_content(model="gemini-3.8-flash", contents=parts,
              config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0)).text)
        m = dict(zip(labels, [Path(f).name for f in order]))
        ranked = [m[l] for l in j["ranking"] if l in m]
        for pos, name in enumerate(ranked):
            borda[name] += len(ranked) - pos
        trials.append({"ranking": ranked, "winner_reason": j.get("winner_reason"),
                       "per_clip": {m.get(k, k): v for k, v in (j.get("per_clip") or {}).items()}})
        print(f"\ntrial {t}: " + " > ".join(x.replace('.wav', '') for x in ranked) + f"\n  winner: {j.get('winner_reason')}")
    print("\nBorda (higher is better):")
    for name, s in sorted(borda.items(), key=lambda kv: -kv[1]):
        print(f"  {name:30s} {s}")
    if a.out:
        Path(a.out).write_text(json.dumps({"objective": rows, "trials": trials, "borda": borda}, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--text-file")
    ap.add_argument("--shuffles", type=int, default=3); ap.add_argument("--out")
    main(ap.parse_args())
