"""Flag segments that sound unlike the rest of the episode ("suddenly a different person").

  python podcast/consistency_check.py --script podcast/script/<ep>_tw.json --segments out/podcast/master/norm_D1_<tag> [--out report.json]

Point it at the mastered per-segment files (out/podcast/master/norm_<voice>_<tag>/, after loudness and tonal match).
Per segment: median pitch, spectral centroid, loudness, speaker similarity to the previous/next segment and to the
episode average (Resemblyzer). A segment is flagged when any of these is off:
  neighbour similarity < 0.93, pitch more than 6 Hz from the episode median,
  centroid more than 350 Hz from the episode median, loudness more than 1 dB from the median.
Fix a flagged segment with:  make_podcast.py episode --only <id> --add-takes 3 ...  then select_takes.py --reuse --consistency.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from compare_voices import load, f0_track, centroid
from make_podcast import measure_lufs, wav_duration

LIMITS = {"neighbour_sim": 0.93, "pitch_hz": 6.0, "centroid_hz": 350.0, "lufs_db": 1.0}

def main(a):
    from resemblyzer import VoiceEncoder, preprocess_wav
    sc = json.loads(Path(a.script).read_text(encoding="utf-8")); d = Path(a.segments)
    ids = [s["id"] for s in sc["segments"]]; paths = [d / f"{i}.wav" for i in ids]
    enc = VoiceEncoder("cpu", verbose=False); E, F, C, L, T = [], [], [], [], []
    t = 3.6   # intro sting + lead-in, then 0.6 s gaps (make_podcast.cmd_master)
    for p in paths:
        x, sr = load(p); e = enc.embed_utterance(preprocess_wav(p)); E.append(e / np.linalg.norm(e))
        F.append(float(np.median(f0_track(x, sr)))); C.append(centroid(x, sr)); L.append(measure_lufs(p)); T.append(t); t += wav_duration(p) + 0.6
    E = np.array(E); mean = E.mean(axis=0); mean /= np.linalg.norm(mean)
    mf, mc, ml = np.median(F), np.median(C), np.median(L); rows = []; flagged = 0
    print(f"{'段落':16s} {'時間':>5s} {'音高':>6s} {'重心':>6s} {'響度':>6s} {'跟上段':>6s} {'跟下段':>6s} {'跟整集':>6s}  問題")
    for k, i in enumerate(ids):
        prev = float(E[k] @ E[k - 1]) if k else None; nxt = float(E[k] @ E[k + 1]) if k < len(ids) - 1 else None
        issues = []
        if prev is not None and prev < LIMITS["neighbour_sim"]: issues.append(f"跟上一段不像 {prev:.3f}")
        if abs(F[k] - mf) > LIMITS["pitch_hz"]: issues.append(f"音高偏 {F[k] - mf:+.1f} Hz")
        if abs(C[k] - mc) > LIMITS["centroid_hz"]: issues.append(f"音色偏{'亮' if C[k] > mc else '暗'} {C[k] - mc:+.0f} Hz")
        if abs(L[k] - ml) > LIMITS["lufs_db"]: issues.append(f"響度偏 {L[k] - ml:+.1f} dB")
        flagged += bool(issues)
        rows.append({"id": i, "start": f"{int(T[k] // 60)}:{int(T[k] % 60):02d}", "pitch_hz": round(F[k], 1), "centroid_hz": round(C[k]),
                     "lufs": round(L[k], 1), "sim_prev": prev and round(prev, 3), "sim_next": nxt and round(nxt, 3),
                     "sim_episode": round(float(E[k] @ mean), 3), "issues": issues})
        print(f"{i:16s} {rows[-1]['start']:>5s} {F[k]:6.1f} {C[k]:6.0f} {L[k]:6.1f} {prev if prev is not None else float('nan'):6.3f} "
              f"{nxt if nxt is not None else float('nan'):6.3f} {rows[-1]['sim_episode']:6.3f}  {'；'.join(issues)}")
    print(f"\n{flagged} 段需要處理" if flagged else "\n全部段落在範圍內")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps({"limits": LIMITS, "segments": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--script", required=True); ap.add_argument("--segments", required=True); ap.add_argument("--out")
    main(ap.parse_args())
