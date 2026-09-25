"""Synthesize the full experiment matrix and log one JSONL row per clip.

  python experiments/run_matrix.py traps      [--models flash,lite] [--voices Kore,tw_female] [--limit N]
  python experiments/run_matrix.py scenarios  [--models flash,lite] [--voices ...]
  python experiments/run_matrix.py cs-realtime [--models flash,lite] [--repeat 3]   # per-turn streaming, telephony 8k mu-law optional

Voice names that appear in out/voices.json are resolved to voice_... IDs; anything else is
treated as a prebuilt voice name (Kore, Puck, Sulafat, ...).
"""
import argparse, json, itertools, time
from pathlib import Path
from tts_client import client, MODELS, synthesize, text_part, write_jsonl, OUT

ROOT = Path(__file__).parent
STYLE_DEFAULT = "自然的台灣國語，語氣親切"

def resolve_voice(name, reg):
    return reg[name]["id"] if name in reg else name

def load_traps():
    return [json.loads(l) for l in (ROOT / "corpus/traps.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

def run_traps(c, models, voices, reg, limit, styles):
    rows = []
    for m, vname, style_on in itertools.product(models, voices, styles):
        for it in load_traps()[:limit]:
            path = OUT / "traps" / f"{it['id']}__{m}__{vname}__{'style' if style_on else 'nostyle'}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            r = synthesize(c, MODELS[m], [text_part(it["text"], STYLE_DEFAULT if style_on else None)],
                           [{"voice": resolve_voice(vname, reg)}], path)
            row = {"exp": "traps", "item": it["id"], "cat": it["cat"], "text": it["text"], "check": it["check"],
                   "model_key": m, "voice": vname, "style": style_on, **r.row()}
            rows.append(row); print(f"{it['id']} {m:5s} {vname:12s} style={style_on} wall={r.wall_s:.1f}s audio={r.audio_s:.1f}s {r.error or ''}")
            write_jsonl(OUT / "traps.jsonl", [row])
    return rows

def run_scenarios(c, models, voices, reg, only=None):
    """Story/dubbing: one request per adjacent speaker pair (max 2 speakers/request).
    Customer service: one request per turn (single speaker)."""
    for f in sorted((ROOT / "corpus/scenarios").glob("*.json")):
        sc = json.loads(f.read_text(encoding="utf-8"))
        if only and sc["id"] != only: continue
        roles = list(sc["speakers"])
        for m in models:
            for vname in voices:
                # map roles to voices: first requested voice for narrator/agent, rest cycle through prebuilt set
                cast = {}
                pool = [vname] + [v for v in ["Sulafat", "Puck", "Zephyr", "Charon", "Leda"] if v != vname]
                for i, role in enumerate(roles):
                    cast[role] = pool[i % len(pool)]
                if len(roles) == 1:
                    for i, t in enumerate(sc["turns"]):
                        st = t.get("style_override") or sc["speakers"][t["speaker"]]["style"]
                        path = OUT / "scenarios" / f"{sc['id']}__{m}__{vname}__t{i:02d}.wav"; path.parent.mkdir(parents=True, exist_ok=True)
                        r = synthesize(c, MODELS[m], [text_part(t["text"], st)], [{"voice": resolve_voice(cast[t["speaker"]], reg)}], path)
                        write_jsonl(OUT / "scenarios.jsonl", [{"exp": "scenario", "scenario": sc["id"], "turn": i, "model_key": m, "voice": vname, "cast": cast, **r.row()}])
                        print(sc["id"], m, vname, i, f"{r.wall_s:.1f}s/{r.audio_s:.1f}s", r.error or "")
                    continue
                # group consecutive turns into chunks that contain at most 2 distinct speakers
                chunks, cur = [], []
                for t in sc["turns"]:
                    if len({x["speaker"] for x in cur} | {t["speaker"]}) > 2:
                        chunks.append(cur); cur = []
                    cur.append(t)
                if cur: chunks.append(cur)
                for ci, ch in enumerate(chunks):
                    spk = sorted({t["speaker"] for t in ch})
                    parts = [text_part(t["text"], t.get("style_override") or sc["speakers"][t["speaker"]]["style"], t["speaker"]) for t in ch]
                    cfg = {"mode": "conversational", "speakers": [{"speaker": s, "voice": resolve_voice(cast[s], reg)} for s in spk]} if len(spk) == 2 \
                          else [{"voice": resolve_voice(cast[spk[0]], reg)}]
                    if len(spk) == 1:
                        parts = [text_part(t["text"], t.get("style_override") or sc["speakers"][t["speaker"]]["style"]) for t in ch]
                    path = OUT / "scenarios" / f"{sc['id']}__{m}__{vname}__c{ci:02d}.wav"; path.parent.mkdir(parents=True, exist_ok=True)
                    r = synthesize(c, MODELS[m], parts, cfg, path)
                    write_jsonl(OUT / "scenarios.jsonl", [{"exp": "scenario", "scenario": sc["id"], "chunk": ci, "speakers": spk, "n_turns": len(ch), "model_key": m, "voice": vname, "cast": cast, **r.row()}])
                    print(sc["id"], m, vname, f"chunk{ci} {spk}", f"{r.wall_s:.1f}s/{r.audio_s:.1f}s", r.error or "")

def run_cs_realtime(c, models, voices, reg, repeat, telephony):
    sc = json.loads((ROOT / "corpus/scenarios/customer_service.json").read_text(encoding="utf-8"))
    st_default = sc["speakers"]["客服"]["style"]
    for m in models:
        for vname in voices:
            for i, t in enumerate(sc["turns"]):
                for k in range(repeat):
                    path = OUT / "cs_realtime" / f"t{i:02d}__{m}__{vname}__r{k}{'__8k' if telephony else ''}.wav"; path.parent.mkdir(parents=True, exist_ok=True)
                    kw = dict(mime_type="audio/mulaw", sample_rate=8000) if telephony else {}
                    r = synthesize(c, MODELS[m], [text_part(t["text"], t.get("style_override") or st_default)],
                                   [{"voice": resolve_voice(vname, reg)}], None if telephony else path, stream=True, **kw)
                    write_jsonl(OUT / "cs_realtime.jsonl", [{"exp": "cs_realtime", "turn": i, "rep": k, "chars": len(t["text"]), "telephony": telephony, "model_key": m, "voice": vname, **r.row()}])
                    print(f"turn{i} {m:5s} {vname:10s} r{k} TTFB={r.ttfb_s and round(r.ttfb_s,2)} wall={r.wall_s:.2f} audio={r.audio_s:.1f} rtf={r.rtf and round(r.rtf,2)} {r.error or ''}")
                    time.sleep(0.3)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=["traps", "scenarios", "cs-realtime"])
    ap.add_argument("--models", default="flash,lite")
    ap.add_argument("--voices", default="Kore")
    ap.add_argument("--limit", type=int, default=10**6)
    ap.add_argument("--styles", default="1,0", help="1=with style annotation, 0=without")
    ap.add_argument("--only", default=None, help="scenario id")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--telephony", action="store_true", help="8 kHz mu-law output (phone line)")
    a = ap.parse_args()
    reg_path = OUT / "voices.json"; reg = json.loads(reg_path.read_text()) if reg_path.exists() else {}
    c = client(); models = a.models.split(","); voices = a.voices.split(",")
    if a.exp == "traps": run_traps(c, models, voices, reg, a.limit, [s == "1" for s in a.styles.split(",")])
    elif a.exp == "scenarios": run_scenarios(c, models, voices, reg, a.only)
    else: run_cs_realtime(c, models, voices, reg, a.repeat, a.telephony)
