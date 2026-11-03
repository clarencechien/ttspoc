"""Rewrite every segment of ep01 into Taiwanese spoken style and assemble podcast/script/ep01_tw.json.

  python podcast/rewrite_episode.py [--n 3] [--model gemini-3.8-flash]

Segments are rewritten in order; each prompt gets the previous segment's last two sentences so the
episode flows, and its position so only the first segment opens the show and only the last one closes it.
Per-segment candidates, lint results and the chosen index go to podcast/script/rewrites/ep01_tw/<id>.json.
Moods are rewritten here to match base_style_v4 (no "lazy", "low voice" or broadcaster cues).
"""
import argparse, hashlib, json, os, re, sys
from pathlib import Path
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from script_lint import lint

MOODS = {
    "s00_open": "開場，輕鬆，像剛按下錄音鍵跟朋友打招呼",
    "s01_copy": "講故事，帶點吐槽",
    "s02_speed": "輕鬆解說，條理清楚",
    "s03_altitude": "先覺得很帥，再恍然大悟",
    "s04_depth": "認真起來，但還是聊天的口氣",
    "s05_judge": "講到外部裁判時語氣認真一點，講到天文案例時興奮起來",
    "s06_range": "幽默，帶點吐槽",
    "s07_resolution": "工程師之間的共鳴，有點無奈",
    "s08_efficacy": "走心，慢一點但不拖",
    "s09_outro": "收尾，輕鬆溫暖",
}

# Signature phrases and how many times the whole episode may use each.
# Once a phrase reaches its cap, later segments are told not to use it, and candidates that do are ranked lower.
PHRASE_CAPS = {"你猜": 3, "重點來了": 2, "醬": 2, "應該說": 1, "有感": 2, "更扯的是": 1, "我看到這": 2, "超扯": 1, "很扯": 1,
               "真的假的": 1, "欸你知道嗎": 1}

def phrase_counts(text):
    return {k: text.count(k) for k in PHRASE_CAPS}

def last_sentences(text, k=2):
    parts = [x for x in re.split(r"(?<=[。？！])", re.sub(r"<[^>]+>", "", text).replace("\n", "")) if x.strip()]
    return "".join(parts[-k:])

def main(a):
    sc = json.loads((ROOT / "script/ep01.json").read_text(encoding="utf-8"))
    body = (ROOT / "prompts/spoken_script_zh-TW.md").read_text(encoding="utf-8").split("\n---\n", 1)[1]
    c = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["gemini_key"])
    outdir = ROOT / "script/rewrites/ep01_tw"; outdir.mkdir(parents=True, exist_ok=True)
    segs = sc["segments"]; new_segments = []; previous = "（這是第一段，沒有上一段）"
    used = {k: 0 for k in PHRASE_CAPS}
    for i, seg in enumerate(segs):
        done = outdir / f"{seg['id']}.json"
        if a.resume and done.exists():
            # container restarts kill long runs: reuse finished segments and rebuild budget + context from them
            rec = json.loads(done.read_text(encoding="utf-8"))
            text = rec["candidates"][rec["chosen"]]["text"].replace("\n", "")
            for k, v in phrase_counts(text).items():
                used[k] += v
            new_segments.append({"id": seg["id"], "mood": MOODS[seg["id"]], "text": text})
            previous = last_sentences(text)
            print(f"{seg['id']:16s} resumed (chose {rec['chosen']})")
            continue
        n = lint(seg["text"])["chars"]
        pos = f"第 {i + 1} 段，共 {len(segs)} 段" + ("（第一段）" if i == 0 else "（最後一段）" if i == len(segs) - 1 else "")
        prompt = (body.replace("{{show}}", sc["show"]).replace("{{audience}}", sc["audience"])
                  .replace("{{source}}", (ROOT / f"script/sources/{seg['id']}.txt").read_text(encoding="utf-8").strip())
                  .replace("{{current}}", seg["text"]).replace("{{position}}", pos).replace("{{previous}}", previous)
                  .replace("{{min_chars}}", str(int(n * 0.8))).replace("{{max_chars}}", str(int(n * 1.2))))
        avoid = [k for k, cap in PHRASE_CAPS.items() if used[k] >= cap]
        prompt = prompt.replace("{{avoid}}", "、".join(f"「{k}」" for k in avoid) if avoid else "（無）")
        cands = []
        for _ in range(a.n):
            t = c.models.generate_content(model=a.model, contents=prompt,
                                          config=types.GenerateContentConfig(temperature=a.temperature)).text.strip()
            cands.append({"text": t, "lint": lint(t)})
        def over_budget(t):
            pc = phrase_counts(t)
            return sum(max(0, used[k] + pc[k] - PHRASE_CAPS[k]) for k in PHRASE_CAPS) + sum(max(0, v - 1) for v in pc.values())
        key = lambda j: (len(cands[j]["lint"]["mainland_words"]), over_budget(cands[j]["text"]),
                         len(cands[j]["lint"]["precise_numbers"]), cands[j]["lint"]["sentences_over_20"],
                         cands[j]["lint"]["avg_sentence_len"])
        best = min(range(len(cands)), key=key)
        for k, v in phrase_counts(cands[best]["text"]).items():
            used[k] += v
        rec = {"segment": seg["id"], "position": pos, "avoid": avoid, "model": a.model, "temperature": a.temperature,
               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "previous_context": previous,
               "original": {"text": seg["text"], "lint": lint(seg["text"])}, "candidates": cands, "chosen": best}
        (outdir / f"{seg['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        text = cands[best]["text"].replace("\n", "")
        new_segments.append({"id": seg["id"], "mood": MOODS[seg["id"]], "text": text})
        previous = last_sentences(text)
        L = cands[best]["lint"]
        print(f"{seg['id']:16s} chose {best}  chars {n}->{L['chars']}  avg_sent {L['avg_sentence_len']}  nums {L['precise_numbers']}  mainland {L['mainland_words']}  avoid {avoid}")
    out = {k: v for k, v in sc.items() if k != "segments"}
    out["episode"] = sc["episode"] + "（台灣口語版）"
    out["note"] = "由 rewrite_episode.py 依 prompts/spoken_script_zh-TW.md 改寫；人工修正記在 script/rewrites/ep01_tw/<id>.json 的 manual_edits"
    out["segments"] = new_segments
    out["phrase_usage"] = used
    (ROOT / "script/ep01_tw.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("phrase usage:", {k: v for k, v in used.items() if v})

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--model", default="gemini-3.8-flash"); ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--resume", action="store_true", help="reuse segments already written to script/rewrites/ep01_tw/")
    main(ap.parse_args())
