"""Turn out/*.jsonl clip logs into a blinded, randomized listening-test manifest.

  python experiments/rating/build_listening_test.py out/traps.jsonl out/scenarios.jsonl --raters 12 --per-rater 40
Produces out/listening/{clips/…, manifest.csv, rater_XX.csv}. Clip files are copied under opaque
names (c0001.wav …) so raters cannot infer model/voice from filenames. manifest.csv is the key.
Design: each rater hears every text item once, in one random condition (Latin-square-ish), plus
2 hidden anchors (a human reference clip and a deliberately bad clip) for attention checks.
"""
import argparse, csv, json, random, shutil
from pathlib import Path

def main(a):
    rows = []
    for f in a.logs:
        rows += [json.loads(l) for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r.get("path") and not r.get("error")]
    rnd = random.Random(a.seed); out = Path(__file__).resolve().parents[2] / "out" / "listening"; (out / "clips").mkdir(parents=True, exist_ok=True)
    key = []
    for i, r in enumerate(rnd.sample(rows, len(rows)), 1):
        cid = f"c{i:04d}"; shutil.copy(r["path"], out / "clips" / f"{cid}.wav")
        key.append({"clip": cid, "item": r.get("item") or f"{r.get('scenario')}:{r.get('turn', r.get('chunk'))}",
                    "cat": r.get("cat", "scenario"), "model": r["model_key"], "voice": r["voice"], "style": r.get("style"), "text": r.get("text", ""), "src": r["path"]})
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=key[0].keys()); w.writeheader(); w.writerows(key)
    by_item = {}
    for k in key: by_item.setdefault(k["item"], []).append(k)
    for rr in range(a.raters):
        picks = [rnd.choice(v) for v in by_item.values()]; rnd.shuffle(picks); picks = picks[:a.per_rater]
        with (out / f"rater_{rr+1:02d}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["order", "clip", "text_shown", "naturalness_1to5", "taiwan_flavor_1to5", "pronunciation_errors(list words)", "emotion_fit_1to5", "would_ship_yes_no", "comment"])
            for o, p in enumerate(picks, 1): w.writerow([o, p["clip"], p["text"], "", "", "", "", "", ""])
    print(f"{len(key)} clips, {a.raters} rater sheets -> {out}. Add anchors manually (see rubric.md).")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("logs", nargs="+"); ap.add_argument("--raters", type=int, default=12)
    ap.add_argument("--per-rater", type=int, default=40); ap.add_argument("--seed", type=int, default=2026)
    main(ap.parse_args())
