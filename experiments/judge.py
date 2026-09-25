"""Automated pre-screen: ask a Gemini multimodal model to transcribe and grade each clip.

NOT the ground truth — the pilot showed it is generous (it heard 「金厲害」 as 「真厲害」 and
still scored 5/5). Use it to (1) catch gross failures (wrong language, truncation, tag read
aloud, garbled Hokkien) before spending human-rater time, and (2) get a rough CER via the
transcript. Final 台灣味 / naturalness scores come from the blind human test.

  python experiments/judge.py out/traps.jsonl [--judge gemini-3.8-flash]
Writes out/<name>.judged.jsonl
"""
import argparse, json, difflib, re
from pathlib import Path
from google.genai import types
from tts_client import client

PROMPT = """你是台灣的語音品質評審。請聽這段音檔並對照原文，用 JSON 回答：
{"transcript": "你聽到的逐字稿",
 "accent": "台灣國語 | 中國大陸普通話 | 混合 | 非中文 | 無法判斷", "accent_confidence": 0到1,
 "mispronunciations": [{"word": "原文詞", "heard": "實際聽到的讀法", "severity": "high|low"}],
 "check_passed": true或false, "check_reason": "針對『檢查重點』一句話說明是否達標",
 "tags_read_aloud": true或false, "truncated": true或false,
 "naturalness_1to5": 1到5, "taiwan_flavor_1to5": 1到5, "notes": "一句話評語"}
原文：{text}
檢查重點：{check}"""

def norm(s):
    return re.sub(r"[\s，。、！？!?,.：:；;「」『』（）()<>\[\]…—-]", "", s or "")

def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r: return None
    sm = difflib.SequenceMatcher(None, r, h)
    return round(1 - sm.ratio(), 3)  # cheap proxy, not true edit distance

def main(a):
    c = client(); src = Path(a.rows); dst = src.with_suffix(".judged.jsonl")
    done = {json.loads(l)["path"] for l in dst.read_text(encoding="utf-8").splitlines()} if dst.exists() else set()
    with dst.open("a", encoding="utf-8") as f:
        for line in src.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if not row.get("path") or row.get("error") or row["path"] in done: continue
            audio = Path(row["path"]).read_bytes()
            text = row.get("text") or ""; check = row.get("check") or "整體自然度與台灣腔"
            r = c.models.generate_content(model=a.judge,
                contents=[types.Part.from_bytes(data=audio, mime_type="audio/wav"), PROMPT.replace("{text}", text).replace("{check}", check)],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            try: j = json.loads(r.text)
            except Exception: j = {"raw": r.text}
            j["cer_proxy"] = cer(text, j.get("transcript", "")) if text else None
            row["judge"] = j
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n"); f.flush()
            print(row.get("item") or row.get("scenario"), row.get("model_key"), row.get("voice"),
                  "accent=", j.get("accent"), "pass=", j.get("check_passed"), "nat=", j.get("naturalness_1to5"), "cer~", j["cer_proxy"])

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("rows"); ap.add_argument("--judge", default="gemini-3.8-flash")
    main(ap.parse_args())
