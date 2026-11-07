"""Re-render chosen turns of a gemini-turns dialogue a few times and keep the clearest take of each.

  python podcast/retake_turns.py --script podcast/dialogue/interview_which_wire.json --voices I=D1,C=IV_M \
      --name B_which-wire_d1-ivm --turns 0,8,11 --takes 3
  python podcast/make_dialogue.py gemini-turns ... --name B_which-wire_d1-ivm     # reassemble (cached turns)

The turns to retake come from dialogue_qa.py ("turns with misses"). Every take, the current one included,
is transcribed alone by Breeze-ASR-25 and scored by misses that do not sound the same with tone, then CER;
takes with a sample glitch (make_dialogue.CLICK) lose. All takes stay in <name>/takes/, the choice in retake.json.
"""
import argparse, json, shutil, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stt_check
from stt_check import norm, cer, misses, real_misses
from make_dialogue import OUT, BC, CLICK, load, parse_voices, resolve, style_for, tts_one, read_wav, client


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--turns", required=True)
    ap.add_argument("--takes", type=int, default=3, help="new takes per turn, on top of the current one")
    a = ap.parse_args()
    from opencc import OpenCC
    from faster_whisper import WhisperModel
    conv = OpenCC("s2twp")
    model = WhisperModel(stt_check.ASR_MODELS["breeze"], device="cpu", compute_type="int8")
    sc = load(a.script); vo = {k: resolve(v) for k, v in parse_voices(a.voices).items()}
    c = client(); d = OUT / a.name; td = d / "takes"; td.mkdir(exist_ok=True)
    log_path = d / "retake.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    tokens = 0
    for i in (int(x) for x in a.turns.split(",")):
        t = sc["turns"][i]; text = BC.sub("", t["text"]); ref = norm(text, conv)
        cur = d / f"turn_{i:02d}.wav"
        n0 = len(list(td.glob(f"turn_{i:02d}_k*.wav")))
        shutil.copy(cur, td / f"turn_{i:02d}_k{n0}.wav")
        for k in range(n0 + 1, n0 + 1 + a.takes):
            tokens += tts_one(c, text, style_for(sc, t), vo[t["speaker"]], td / f"turn_{i:02d}_k{k}.wav")
        rows = []
        for p in sorted(td.glob(f"turn_{i:02d}_k*.wav")):
            hyp = norm("".join(s.text for s in model.transcribe(str(p), language="zh", beam_size=5, vad_filter=True)[0]), conv)
            ms = real_misses(misses(ref, hyp))
            glitch = float(np.abs(np.diff(read_wav(p))).max()) > CLICK
            rows.append({"take": p.name, "misses": [m["context"] + " → " + m["heard"] for m in ms],
                         "cer": round(cer(ref, hyp), 3), "glitch": glitch, "heard": hyp})
        best = min(rows, key=lambda r: (r["glitch"], len(r["misses"]), r["cer"]))
        shutil.copy(td / best["take"], cur)
        log[f"{i:02d}"] = {"text": text, "chosen": best["take"], "takes": rows}
        print(f"turn {i:02d}: chose {best['take']}  " + "  ".join(f"{r['take'][-6:-4]}:{len(r['misses'])}/{r['cer']:.0%}{'!' if r['glitch'] else ''}" for r in rows))
        for m in best["misses"]:
            print("    still:", m)
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("tokens", tokens)


if __name__ == "__main__":
    main()
