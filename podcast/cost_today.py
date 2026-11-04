"""Gemini spend on 2026-11-03 (the podcast day), itemised, plus the steady-state cost of one episode.

  python podcast/cost_today.py

Paid-tier list prices through 2026-12-31 (they double on 2027-01-01):
  gemini-3.8-flash-tts   text in 0.50 / 1M, audio out 9.00 / 1M, 25 audio tokens per second
  gemini-3.8-flash       input 0.75 / 1M (audio in = 32 tokens per second), output incl. thinking 3.75 / 1M
Measured usage per call (2026-11-03): rewrite 1,720 in / 2,677 out; 40 s QA 1,330 in / 1,153 out;
voice design ~969 thinking tokens on top of the sample audio.
TTS seconds come from the WAVs still in out/podcast (98.8 min) plus renders whose files were lost to container
restarts or overwritten (listed below). Judge and STT calls are counted from the runs made that day.
If the key is on the free tier, the real charge is 0; the AI Studio usage page is the source of truth.
"""
TTS_OUT, TTS_IN = 9.00, 0.50
FL_IN, FL_OUT = 0.75, 3.75

def tts(seconds, calls, text_tokens=600):
    return seconds * 25 / 1e6 * TTS_OUT + calls * text_tokens / 1e6 * TTS_IN

def flash(calls, audio_s=0.0, text_in=500, out=1200):
    return (audio_s * 32 + calls * text_in) / 1e6 * FL_IN + calls * out / 1e6 * FL_OUT

ITEMS = [
    # --- speech generation (gemini-3.8-flash-tts)
    ("語音", "留存的音檔：試聽、設計樣本、第一版兩集、台灣口語版、修正版 36 次、行星段實驗、一次生成、測試集", tts(98.8 * 60, 200)),
    ("語音", "已遺失或被覆蓋：第一版重念 4 段、另一個 session 的試聽 2 段、漂移測試 28 段、D1 重現 13 次", tts(14.7 * 60, 47)),
    ("語音", "設計聲線 7 個的思考 token（D1、D2、重現 3、remix 2）", 7 * 969 / 1e6 * TTS_OUT),
    # --- gemini-3.8-flash listening to audio
    ("評審", "選聲：單段評分 6、比較排名 3", flash(6, 124) + flash(3, 372, 800, 3000)),
    ("評審", "第一版兩集逐段校對 24 次", flash(24, 1186, 400, 1150)),
    ("評審", "另一個 session：ElevenLabs 比較排名 3、校對 10", flash(3, 456, 800, 3000) + flash(10, 434, 400, 1150)),
    ("評審", "行星段：A/B 4、聽後測驗 2、語氣排名 3、磁性排名 3、口音排名 3", flash(4, 520, 800, 3000) + flash(2, 130) + flash(9, 3540, 800, 3000)),
    ("盲聽", "Whisper 搭配的 Gemini 盲聽：台灣口語版 Gemini 3 輪、ElevenLabs 3 輪（各 10 段）", flash(30, 1494) + flash(30, 1353)),
    ("盲聽", "Breeze 搭配的 Gemini 盲聽：Gemini 修正前後、Hardy（各 10 段）", flash(30, 1508)),
    ("盲聽", "ElevenLabs 調整 4、聲音庫 7、測試集 2、量測 1", flash(14, 372)),
    # --- gemini-3.8-flash writing
    ("改寫", "改寫稿子：行星段 5、整集兩輪 60、量測 1、測試集 4", flash(70, 0, 2500, 2700)),
]

def episode(candidates=3, takes=3, seconds=520, extra=0.1):
    rewrite = flash(10 * candidates, 0, 2500, 2700)
    voice = tts(seconds * takes, 10 * takes) * (1 + extra)
    check = flash(10, seconds, 500, 1200)
    return rewrite, voice, check

if __name__ == "__main__":
    groups = {}
    for g, label, c in ITEMS:
        groups[g] = groups.get(g, 0) + c
        print(f"  {c:6.3f}  {g:4s} {label}")
    total = sum(groups.values())
    print("小計：" + "、".join(f"{g} {v:.2f}" for g, v in groups.items()) + f"；今天合計 {total:.2f} 美元")
    r, v, q = episode()
    print(f"\n之後一集（PIPELINE.md 流程）：改寫 {r:.2f} + 語音 {v:.2f} + 盲聽 {q:.2f} = {r + v + q:.2f} 美元；2027 年起 {2 * (r + v + q):.2f}")
    r1, v1, q1 = episode(candidates=1, takes=2)
    print(f"精簡版（1 個候選稿、每段 2 次）：{r1 + v1 + q1:.2f} 美元；2027 年起 {2 * (r1 + v1 + q1):.2f}")
