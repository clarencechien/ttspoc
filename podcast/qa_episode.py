"""Per-segment QA for a generated episode: transcript diff, misreadings, tags read aloud, F0 drift.

  python podcast/qa_episode.py S3 D1
Writes out/podcast/qa_<voice>.json and prints a summary table.
"""
import difflib, json, os, re, sys
from pathlib import Path
import numpy as np
from google import genai
from google.genai import types
sys.path.insert(0, str(Path(__file__).parent))
from compare_voices import load, f0_track

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "podcast"
SCRIPT = json.loads((ROOT / "podcast/script/ep01.json").read_text(encoding="utf-8"))
PROMPT = """你是台灣 podcast 的後製校對。聽這段音檔、對照原稿，只輸出 JSON：
{"transcript": "你實際聽到的逐字稿（照實寫，含唸錯）",
 "misreadings": [{"word": "原稿詞", "heard": "實際唸法", "severity": "high 或 low"}],
 "tags_read_aloud": true或false, "skipped_or_added": "漏念或多念的內容，沒有就空字串",
 "mainland_accent_moments": "聽起來像中國大陸腔的地方，沒有就空字串",
 "english_terms_issue": "英文技術名詞唸得怪的地方，沒有就空字串"}
原稿（尖括號是音效標籤，不該被唸出來）：{text}"""

def norm(s):
    return re.sub(r"<[^>]+>|[^\w]", "", s)

def main(voices, only=None):
    c = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])
    for v in voices:
        rows = []
        prev = {r["id"]: r for r in json.loads((OUT / f"qa_{v}.json").read_text())} if only and (OUT / f"qa_{v}.json").exists() else {}
        for s in SCRIPT["segments"]:
            if only and s["id"] not in only and s["id"] in prev:
                rows.append(prev[s["id"]]); continue
            p = OUT / "segments" / v / f"{s['id']}.wav"
            r = c.models.generate_content(model="gemini-3.8-flash",
                contents=[types.Part.from_bytes(data=p.read_bytes(), mime_type="audio/wav"), PROMPT.replace("{text}", s["text"])],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            j = json.loads(r.text)
            sim = difflib.SequenceMatcher(None, norm(s["text"]), norm(j.get("transcript", ""))).ratio()
            x, sr = load(p); f0 = f0_track(x, sr)
            rows.append({"id": s["id"], "f0_median": round(float(np.median(f0)), 1), "text_match": round(sim, 3), **j})
        (OUT / f"qa_{v}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        f0s = [r["f0_median"] for r in rows]
        print(f"\n=== {v}: F0 median across segments {min(f0s)}–{max(f0s)} Hz (spread {max(f0s)-min(f0s):.1f})")
        for r in rows:
            mis = "; ".join(f"{m['word']}→{m['heard']}({m['severity'][0]})" for m in r.get("misreadings", []))
            flags = " ".join(f for f, on in [("TAG!", r.get("tags_read_aloud")), ("SKIP:" + r.get("skipped_or_added", ""), r.get("skipped_or_added")),
                                             ("CN:" + r.get("mainland_accent_moments", ""), r.get("mainland_accent_moments")),
                                             ("EN:" + r.get("english_terms_issue", ""), r.get("english_terms_issue"))] if on)
            print(f"{r['id']:16s} F0={r['f0_median']:6.1f} match={r['text_match']:.2f} {mis} {flags}")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--only=")]
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv[1:] if a.startswith("--only=")), None)
    main(args, only)
