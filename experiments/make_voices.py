"""Create the designed voices used by the experiment and write their IDs to out/voices.json.

Conditions (all store=True; the API rejects store=False for prompted voices):
  tw_female / tw_male       – prompt explicitly asks for 台灣國語, language_code zh-TW
  ctrl_female / ctrl_male   – same persona, NO accent instruction, language_code zh-TW  (does the prompt matter?)
  cn_female                 – same persona, language_code zh-CN, no accent instruction (negative control)
Prebuilt studio voices (Kore/Puck/Sulafat/…) need no creation and are the baseline.
Voice replication (30 s sample + consent phrase) is deliberately left out: it needs a consenting
Taiwanese speaker and is unavailable in EEA/UK/CH/IN/IL/TX; add it as condition `rep_*` if you have one.
"""
import base64, json, sys
from pathlib import Path
from tts_client import client, OUT

OUT.mkdir(exist_ok=True)
PERSONA = {
    "female": "三十歲左右的女生，聲音溫暖、親切、清楚，適合說故事也適合客服。",
    "male": "三十五歲左右的男生，聲音沉穩、有精神、清楚，適合旁白也適合客服。",
}
TW_HINT = "使用標準台灣國語（台灣腔），語助詞自然，不要中國大陸的捲舌腔和兒化音。"
SPECS = {
    "tw_female":   ("female", "zh-TW", PERSONA["female"] + TW_HINT),
    "tw_male":     ("male",   "zh-TW", PERSONA["male"] + TW_HINT),
    "ctrl_female": ("female", "zh-TW", PERSONA["female"]),
    "ctrl_male":   ("male",   "zh-TW", PERSONA["male"]),
    "cn_female":   ("female", "zh-CN", PERSONA["female"]),
}

def main(model="gemini-3.8-flash-tts"):
    c = client()
    reg_path = OUT / "voices.json"
    reg = json.loads(reg_path.read_text()) if reg_path.exists() else {}
    for key, (gender, lc, prompt) in SPECS.items():
        if key in reg:
            print("exists", key, reg[key]["id"]); continue
        v = c.voices.create(store=True, voice={
            "model": model, "type": "prompted", "display_name": f"ttspoc-{key}",
            "gender": gender, "language_code": lc, "prompted": {"input": prompt}})
        d = v.model_dump()
        (OUT / f"voice_sample_{key}.wav").write_bytes(base64.b64decode(d["sample_audio"]["data"]))
        reg[key] = {"id": d["id"], "language_code": lc, "gender": gender, "prompt": prompt,
                    "expire_time": str(d.get("expire_time"))}
        reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=1))
        print("created", key, d["id"])
    print("registry:", reg_path)

if __name__ == "__main__":
    main(*sys.argv[1:])
