"""Real-time vs batch envelope: TTFB / RTF vs input length, unary vs streaming, both models.

  python experiments/bench_latency.py [--repeat 3] [--lengths 20,60,200,600,2000]
Lengths are in Chinese characters; text is built by repeating a neutral Taiwan-Mandarin paragraph.
Also probes the ceiling: how many characters before the 8,192 input-token / 16,384 output-token
limits bite (the last length that returns without error or truncation).
"""
import argparse, statistics, json
from pathlib import Path
from tts_client import client, MODELS, synthesize, text_part, write_jsonl, OUT

PARA = ("從前從前，在山腳下的一個小村莊裡，住著一對姊妹。有一天晚上，媽媽出門去外婆家，只留下姊妹倆在家。"
        "門外忽然傳來敲門聲，姊姊阿珠從門縫偷偷看出去，只見一個陌生的老婆婆站在月光底下，笑咪咪地看著她。")

def build(n):
    s = ""
    while len(s) < n: s += PARA
    return s[:n]

def main(a):
    c = client(); out = OUT; out.mkdir(exist_ok=True)
    for n in [int(x) for x in a.lengths.split(",")]:
        text = build(n)
        for m in a.models.split(","):
            for mode in ("stream", "unary"):
                rs = []
                for k in range(a.repeat):
                    path = out / "latency" / f"{n}c__{m}__{mode}__r{k}.wav"; path.parent.mkdir(parents=True, exist_ok=True)
                    r = synthesize(c, MODELS[m], [text_part(text, "自然的台灣國語旁白")], [{"voice": "Kore"}], path, stream=(mode == "stream"))
                    rs.append(r)
                    write_jsonl(out / "latency_runs.jsonl", [{"chars": n, "model_key": m, "rep": k, **r.row()}])  # per-run rows, audio kept for drift/loop checks
                ok = [r for r in rs if not r.error]
                row = {"chars": n, "model_key": m, "mode": mode, "n": len(ok), "errors": [r.error for r in rs if r.error],
                       "ttfb_med": statistics.median(r.ttfb_s for r in ok) if ok and mode == "stream" else None,
                       "wall_med": statistics.median(r.wall_s for r in ok) if ok else None,
                       "audio_med": statistics.median(r.audio_s for r in ok) if ok else None,
                       "rtf_med": statistics.median(r.rtf for r in ok) if ok else None,
                       "in_tok": ok[0].input_tokens if ok else None, "out_tok": ok[0].output_tokens if ok else None}
                write_jsonl(out / "latency.jsonl", [row])
                print(json.dumps(row, ensure_ascii=False))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="lite,flash"); ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--lengths", default="20,60,200,600,2000")
    main(ap.parse_args())
