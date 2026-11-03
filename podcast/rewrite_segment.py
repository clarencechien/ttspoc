"""Rewrite one segment of the episode script into spoken style with prompts/spoken_script_zh-TW.md.

  python podcast/rewrite_segment.py s05_judge [--model gemini-3.8-flash] [--n 1]

Source material for the segment is read from podcast/script/sources/<segment_id>.txt (article excerpt).
Writes podcast/script/rewrites/<segment_id>.json with the prompt hash, model, settings, every candidate
and its lint report, so the rewrite is reproducible and auditable.
"""
import argparse, hashlib, json, os, sys
from pathlib import Path
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from script_lint import lint

def main(a):
    sc = json.loads((ROOT / "script/ep01.json").read_text(encoding="utf-8"))
    seg = next(s for s in sc["segments"] if s["id"] == a.segment)
    tpl = (ROOT / "prompts/spoken_script_zh-TW.md").read_text(encoding="utf-8")
    prompt_body = tpl.split("\n---\n", 1)[1]           # drop the file's own header
    n = lint(seg["text"])["chars"]
    prompt = (prompt_body.replace("{{show}}", sc["show"]).replace("{{audience}}", sc["audience"])
              .replace("{{source}}", (ROOT / f"script/sources/{a.segment}.txt").read_text(encoding="utf-8").strip())
              .replace("{{current}}", seg["text"])
              .replace("{{position}}", "單獨一段（測試用）").replace("{{previous}}", "（無）").replace("{{avoid}}", "（無）")
              .replace("{{min_chars}}", str(int(n * 0.8))).replace("{{max_chars}}", str(int(n * 1.2))))
    c = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])
    out = {"segment": a.segment, "model": a.model, "temperature": a.temperature,
           "prompt_file": "podcast/prompts/spoken_script_zh-TW.md",
           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
           "original": {"text": seg["text"], "lint": lint(seg["text"])}, "candidates": []}
    for i in range(a.n):
        r = c.models.generate_content(model=a.model, contents=prompt,
                                      config=types.GenerateContentConfig(temperature=a.temperature))
        text = r.text.strip()
        out["candidates"].append({"text": text, "lint": lint(text)})
        print(f"\n--- candidate {i}\n{text}\n{json.dumps(lint(text), ensure_ascii=False)}")
    # pick the candidate with no mainland words first, then fewest precise numbers, then shortest sentences
    key = lambda i: (len(out["candidates"][i]["lint"]["mainland_words"]), len(out["candidates"][i]["lint"]["precise_numbers"]),
                     out["candidates"][i]["lint"]["avg_sentence_len"])
    out["chosen"] = min(range(len(out["candidates"])), key=key)
    print(f"\nchosen candidate: {out['chosen']}")
    d = ROOT / "script/rewrites"; d.mkdir(parents=True, exist_ok=True)
    name = f"{a.segment}_{a.tag}" if a.tag else a.segment
    (d / f"{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("segment"); ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--n", type=int, default=1); ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--tag", default="", help="suffix for the output file, so earlier rewrites are kept")
    main(ap.parse_args())
