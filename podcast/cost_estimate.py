"""Cost of the whole TTS POC so far, and of one future episode, at paid-tier list prices.

  python podcast/cost_estimate.py

Prices (USD, checked 2026-11-03; Gemini paid rates double on 2027-01-01):
  gemini-3.8-flash-tts       text in 0.50 / 1M, audio out 9.00 / 1M; audio out = 25 tokens per second
  gemini-3.8-flash-lite-tts  text in 0.50 / 1M, audio out 6.00 / 1M
  gemini-3.8-flash           input 0.75 / 1M (audio in = 32 tokens per second), output incl. thinking 3.75 / 1M
  ElevenLabs v3 / v4         0.08 per 1,000 characters (or drawn from a plan's included characters)
Measured on 2026-11-03: one rewrite call = 1,720 in + 2,677 out (2,536 of it thinking);
one 40 s QA call = 1,330 in + 1,153 out (925 thinking).
Where no log survived, counts are reconstructed from the scripts that ran; they are estimates.
"""
TTS_OUT = {"flash": 9.00, "lite": 6.00}; TTS_IN = 0.50
FLASH_IN, FLASH_OUT = 0.75, 3.75
EL_PER_1K = 0.08
AUDIO_OUT_TPS, AUDIO_IN_TPS = 25, 32

def tts(seconds, model="flash", calls=0, text_tokens=400):
    return seconds * AUDIO_OUT_TPS / 1e6 * TTS_OUT[model] + calls * text_tokens / 1e6 * TTS_IN

def flash(calls, in_tokens, out_tokens, audio_seconds=0):
    return (calls * in_tokens + audio_seconds * AUDIO_IN_TPS) / 1e6 * FLASH_IN + calls * out_tokens / 1e6 * FLASH_OUT

# ---- whole POC: (label, group, cost) ----
items = [
    # September: TTS experiments (experiments/pilot)
    ("9 月實驗：冒煙測試、短句延遲、陷阱句、客服逐句（Flash 一半、Lite 一半）", "Gemini TTS", tts(165, "flash", 50) + tts(165, "lite")),
    ("9 月實驗：長文延遲基準 60/600/2000 字", "Gemini TTS", tts(1000, "flash", 12) + tts(1000, "lite", 12)),
    ("9 月實驗：設計聲線探測、雙人故事", "Gemini TTS", tts(33, "flash", 2)),
    ("9 月實驗：音檔評審 12 次", "Gemini 評審", flash(12, 400, 1150, 91)),
    # November: podcast
    ("設計聲線 8 個（D1、D2、remix 2 個、重現測試 3 個、9 月探測 1 個）", "Gemini TTS", 8 * (1357 / 1e6 * TTS_OUT["flash"])),
    ("選聲試聽 6 個 + 第二輪基準 2 個", "Gemini TTS", tts(166, "flash", 8)),
    ("第一版整集兩個聲線 + 重做 4 段", "Gemini TTS", (11950 + 12445) / 1e6 * TTS_OUT["flash"] + tts(210, "flash", 24)),
    ("跨模型漂移測試 28 段", "Gemini TTS", tts(280, "flash", 28)),
    ("D1 重現測試：3 個設計 + 10 段", "Gemini TTS", tts(203, "flash", 11)),
    ("行星段：改寫與語氣調整 21 段", "Gemini TTS", tts(1156, "flash", 21)),
    ("台灣口語版整集：10 段各 2 次", "Gemini TTS", tts(1001, "flash", 20, 600)),
    ("評審與校對：單段 53 次", "Gemini 評審", flash(53, 400, 1150, 3216)),
    ("評審：多段比較排名與 A/B 19 次", "Gemini 評審", flash(19, 600, 3000, 4168)),
    ("改寫稿子約 66 次（單段測試、整集兩輪、量測）", "Gemini 改寫", flash(66, 2500, 2700)),
    ("ElevenLabs：設計 3 個預覽、試聽 6 段、整集 10 段，約 3,660 字元", "ElevenLabs", 3660 / 1000 * EL_PER_1K),
]

def episode(candidates=3, takes=2, seconds=500, tts_model="flash", engine="gemini", chars=2400):
    rewrite = flash(10 * candidates, 2500, 2700)
    voice = (tts(seconds * takes, tts_model, 10 * takes, 600) * 1.1) if engine == "gemini" else chars * takes / 1000 * EL_PER_1K
    qa = flash(10, 400, 1150, seconds)
    return rewrite, voice, qa

if __name__ == "__main__":
    print("== 整個 POC（付費價，2026 年底前費率）")
    groups = {}
    for label, g, c in items:
        groups[g] = groups.get(g, 0) + c
        print(f"  {c:7.3f}  {g:10s} {label}")
    total = sum(groups.values())
    print("  小計：" + "、".join(f"{g} {v:.2f}" for g, v in groups.items()) + f"；合計 {total:.2f} 美元")
    print("\n== 之後一集（約 8.5 分鐘、2,400 字）")
    for name, kw in [("目前流程：3 個候選稿、每段 2 次、逐段校對", {}),
                     ("精簡：1 個候選稿、每段 1 次、逐段校對", {"candidates": 1, "takes": 1}),
                     ("目前流程，但語音改用 Flash-Lite TTS", {"tts_model": "lite"}),
                     ("目前流程，但語音改用 ElevenLabs v4", {"engine": "elevenlabs"})]:
        r, v, q = episode(**kw); t = r + v + q
        print(f"  {name:36s} 改寫 {r:.2f} + 語音 {v:.2f} + 校對 {q:.2f} = {t:.2f} 美元；2027 年起 Gemini 部分加倍，約 {t + (r + q + (v if kw.get('engine') != 'elevenlabs' else 0)):.2f}")
