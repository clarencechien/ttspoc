"""Match a new clip against the saved reference recordings (podcast/samples/references).

Use this when a model is retired or upgraded: generate the reference text with each candidate
voice on the new model, then pick the candidate whose speaker embedding is closest to the old reference.

  python podcast/match_voice.py build                     # (re)compute embeddings in references.json
  python podcast/match_voice.py match new_clip.wav [...]  # cosine similarity of each clip to every reference

Speaker embeddings come from Resemblyzer (English-trained d-vector, 256 dims). It needs torch, which is
heavy, so it is not in requirements.txt:
  python3 -m pip install --index-url https://download.pytorch.org/whl/cpu torch && python3 -m pip install resemblyzer
Scale observed on 2026-11-03 (Gemini, same sentence, 3 takes each):
  same model + same voice ~0.93, same voice one model generation apart ~0.87-0.90,
  different voice ~0.79-0.81. Treat it as a ranking signal, not an absolute threshold.
"""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
REF_DIR = ROOT / "samples" / "references"
REF_JSON = REF_DIR / "references.json"


def to_wav(path):
    """Decode any format (flac/mp3/wav) to 16 kHz mono wav via ffmpeg."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", tmp], check=True)
    return tmp


def embed(path, enc=None):
    from resemblyzer import VoiceEncoder, preprocess_wav
    enc = enc or VoiceEncoder("cpu", verbose=False)
    e = enc.embed_utterance(preprocess_wav(to_wav(path)))
    return e / np.linalg.norm(e), enc


def f0_median(path):
    sys.path.insert(0, str(ROOT))
    from compare_voices import load, f0_track
    x, sr = load(to_wav(path))
    f0 = f0_track(x, sr)
    return round(float(np.median(f0)), 1) if len(f0) else None


def cmd_build():
    meta = json.loads(REF_JSON.read_text(encoding="utf-8"))
    enc = None
    for r in meta["references"]:
        p = REF_DIR / r["file"]
        e, enc = embed(p, enc)
        r["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        r["f0_median_hz"] = f0_median(p)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                             capture_output=True, text=True).stdout.strip()
        r["duration_s"] = round(float(dur), 2)
        r["embedding_resemblyzer"] = [round(float(v), 5) for v in e]
        print(f"{r['file']:44s} F0={r['f0_median_hz']} dur={r['duration_s']}s")
    REF_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_match(files):
    meta = json.loads(REF_JSON.read_text(encoding="utf-8"))
    enc = None
    refs = [(r["file"], np.array(r["embedding_resemblyzer"])) for r in meta["references"]]
    for f in files:
        e, enc = embed(f, enc)
        scores = sorted(((float(np.dot(e, v)), name) for name, v in refs), reverse=True)
        print(f"\n{f}")
        for s, name in scores:
            print(f"  {s:.3f}  {name}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("build", "match"):
        sys.exit(__doc__)
    if sys.argv[1] == "build":
        cmd_build()
    else:
        cmd_match(sys.argv[2:])
