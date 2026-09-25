# ttspoc — Gemini 3.8 TTS 台灣風味實驗

目標：搞清楚 Google 2026-09-23 發表的 **Gemini 3.8 Flash TTS / Flash-Lite TTS** 更新了什麼、兩者差在哪、
拿來做**即時**（客服）與**批次**（念故事、配音）應用的限制，以及**台灣風味**（台灣國語、台語詞、台灣用語、台灣讀音）到底行不行，
並用一套可重跑的實驗來回答。

> 狀態：文獻整理 + API 探測 + 小規模 pilot 已完成（2026-09-25）。完整矩陣與人類盲測尚未執行，腳本都在 `experiments/`。

---

## 1. 這次更新了什麼（vs Gemini 3.1 Flash TTS）

| 項目 | 3.1 Flash TTS (preview) | 3.8 Flash TTS | 3.8 Flash-Lite TTS |
|---|---|---|---|
| Model ID | `gemini-3.1-flash-tts-preview` | `gemini-3.8-flash-tts` | `gemini-3.8-flash-lite-tts` |
| 定位 | 前一代 | 「深度創意指導與角色設計」：錄音室級音質、演技、口音/方言 | 「高量、低成本、低延遲」：客服語音代理、大量朗讀、配音 |
| 語言 | ~70 | 130+ | 101 |
| 聲線 | 30 個 studio 聲線 | 30 studio + **Extended Voice Library 2,089 個** + 語音設計 + 語音複製 | 同左 |
| 語音設計（文字描述生聲線） | 無 | 有（`voices.create type=prompted`，必須 `store=true`，回 `voice_…` ID，效期 1 年，每專案 200 個） | 有 |
| 語音複製 | 無 | 有（15–30 秒樣本 + 同意句朗讀；`store=false` 回 7 天效期 `voicekey_…`；**伊利諾、德州、EEA、英國、瑞士、印度不開放**） | 有 |
| 導演式控制 | prompt 內夾指令 | 逐句 `speech_metadata.style`（持續狀態：語氣、語速、耳語）+ 行內 `<laugh>` `<sigh>` `<short pause>` `<whisper>`（瞬間事件） | 同左 |
| 雙人對話 | 有 | `mode: conversational`，**單一請求最多 2 個 prebuilt 說話者**；設計/複製聲線只能單人 | 同左 |
| 長文穩定度 | 會漂 | 官方稱 speaker drift 大幅改善 | 同左 |
| 輸出格式 | raw PCM | 預設 **WAV 24 kHz 16-bit**（unary）/ raw L16（streaming）；可選 mu-law、A-law、8k/16k/24k | 同左 |
| API | generateContent | **Interactions API** (`/v1beta/interactions`)，不再走 generateContent | 同左 |
| Hume AI Overall Quality | 0.783 | **0.920**（#1） | 0.914（#2） |
| 輸入/輸出上限 | 32k session | **8,192 input tokens / 16,384 output tokens** | 同左 |
| 價格（到 2026-12-31；2027-01-01 起翻倍） | $1 / $20 | $0.50 text in / **$9** audio out（batch $4.50） | $0.50 / **$6**（batch $3） |
| SynthID 浮水印 | – | 全部音檔都有 | 全部音檔都有 |

**Flash vs Lite 的真正差異**（官方只講定位，不給數字）：
- 功能表完全一樣（單人、雙人、設計、複製、快取、Batch、Flex、Priority 都支援；都不支援 Live API）。
- 差在音質/演技上限、語言數（130 vs 101）、價格（1.5×）、以及我們實測出來的**速度**（見 §3，Lite 快 2–3 倍）。
- 官方模型卡：Flash 強調 "maximum voice fidelity, acting nuance, and dialect coverage"；Lite 強調 "high throughput, low latency, cost efficiency"，並明說 Lite 是 3.1 preview 的正式替代品。

---

## 2. 即時 vs 批次：限制到底多大

### 2.1 即時（客服 / 語音代理）
| 面向 | 事實 | 影響 |
|---|---|---|
| 串流 | 支援 `stream=true`，audio chunk 邊生成邊送 | 可以做「講到一半就開始播」 |
| **沒有 Live API / 雙向串流** | 兩個模型都標示 Live API 不支援 | 每一句要等 LLM 把文字生完才能送 TTS；文字端要自己做 sentence-level chunking |
| TTFB（實測，雲端容器→Google） | **Lite 中位 1.0 s (p90 1.13)；Flash 中位 1.66 s (p90 1.96)**；最短一次 Lite 0.48 s | 客服「可接受」門檻通常 ≤ 1–1.5 s：Lite 勉強及格、Flash 不及格。加上 LLM 首句延遲後，整體體感會超過 2 s |
| RTF（生成時間 / 音長） | **Lite 0.35 (max 0.63)；Flash 0.92 (max 1.78)** | Flash 串流有時**比即時還慢**（音會斷），不適合即時；Lite 有 3 倍餘裕 |
| 電話線路 | 可直接輸出 8 kHz mu-law / A-law | 省一次轉碼；SIP/Twilio 可直接接 |
| Rate limit | 文件不公布數字，只能到 AI Studio 看自己專案的 tier；3.1 起是「動態吞吐量限制」 | 上線前一定要在自己 tier 壓測；論壇有人回報付費 key 比 AI Studio key 慢 10 倍的異常 |
| 雙人 | 客服不需要 | – |
| 每請求上限 | 8,192 input tokens（中文 ≈ 1 token/字 → 約 8,000 字） | 客服單句遠低於此 |

### 2.2 批次（念故事 / 配音 / 有聲書）
| 面向 | 事實 | 影響 |
|---|---|---|
| 單請求輸出上限 | 16,384 audio tokens；實測 **32–40 tokens/秒** → **每請求約 7–8.5 分鐘音檔**（Cloud TTS 文件寫 ~655 s 會截斷） | 一章 5,000 字（≈20 分鐘）要切成 3–4 段；切段間的聲線一致性要靠同一個 `voice_…` ID + 同一個 style 字串，實驗要驗 drift |
| 單請求輸入上限 | 8,192 tokens ≈ 8,000 中文字 | 通常先撞到輸出上限，不會撞到輸入 |
| 雙人限制 | 一次最多 2 個 prebuilt 說話者；設計/複製聲線不能同時多人 | 三人以上的故事要拆成「旁白+A」「旁白+B」再剪接（`run_matrix.py` 已自動切） |
| Batch API | 模型卡寫「支援」，價格頁有 batch 價（半價）；但 Batch API 文件目前只列 generateContent | **需驗證** interactions TTS 能否進 Batch；不行的話用 Flex inference（同樣半價，較慢） |
| 週轉 | Batch 目標 24 小時內，實務上快很多 | 有聲書隔夜跑即可 |
| 成本（32 tok/s，含文字） | Lite 線上 **$0.70/小時**、批次 $0.35；Flash 線上 $1.04、批次 $0.53；**2027 起翻倍** | 100 小時有聲書：Lite 批次 $35、Flash 批次 $53。100 萬通客服 6 秒回應：Lite $1,164、Flash $1,740 |

### 2.3 台灣風味的現況（探測結果，非常重要）
1. **Extended Voice Library 2,089 個聲線裡，中文為 0 個。** 30 個 language_code 全是 en/ja/ko/hi/pt/ar/de/es/fr/pl/it/…，沒有 zh-TW、zh-CN、cmn、yue。30 個 studio 聲線（Kore、Puck…）全標 en-US，但它們是多語聲線，中文照講。
2. 所以中文只有三條路：**(a) studio 聲線直接講中文**、**(b) 語音設計**（`language_code: "zh-TW"` 被接受，回傳的 sample 被評審判為台灣國語 0.95）、**(c) 語音複製**（找台灣配音員錄 30 秒 + 同意句）。
3. 模型卡的語言表只寫 "Chinese (Hant script)"、"Chinese (Hans script)"、Cantonese，**沒有「台灣」這個維度**；口音靠 style/設計 prompt 引導。
4. Pilot（8 段陷阱句 + 客服句）自動評審全部判為台灣國語（信心 0.95–0.98），語助詞「欸/喔/齁/啦/蛤/捏」自然。
5. **弱點已浮現：台語漢字。**「歹勢」兩個模型都用國語讀（dǎi-shì / tái-sè）；改寫成諧音「拍謝」就正確。「呷飽未」「金厲害」在雙人故事中有唸出台語感（評審把「金」聽成「真」，存疑）。→ 實驗要系統性測台語漢字 vs 諧音 vs 台羅。

---

## 3. Pilot 數據（2026-09-25，n 很小，只當方向）

客服腳本 6 句 × 2 次，串流，Kore（`experiments/pilot/cs_realtime_pilot.json`）：

| 模型 | TTFB 中位 | TTFB p90 | RTF 中位 | RTF 最大 |
|---|---|---|---|---|
| flash-lite | 1.00 s | 1.13 s | 0.35 | 0.63 |
| flash | 1.66 s | 1.96 s | 0.92 | 1.78 |

其他：unary 60 字句兩模型都約 6 s；雙人故事 3 turn（20 秒音）Lite 7.4 s；語音設計一次約 10 s 含 sample。詳見 `experiments/pilot/smoke_first_run.md`。

---

## 4. 實驗設計

### 4.1 研究問題
- **RQ1 台灣味**：Flash / Lite 用 studio 聲線、zh-TW 設計聲線、無口音指示的設計聲線、zh-CN 對照聲線，台灣母語者盲測的「台灣味」與 MOS 各多少？style 標註有沒有差？
- **RQ2 陷阱通過率**：10 類台灣陷阱（語助詞、台語漢字、台羅、中英夾雜、台灣用語、台灣讀音、人名地名、數字、演技標籤、客服句）各類的發音正確率；哪一類該用改寫（如 歹勢→拍謝）繞過？
- **RQ3 即時可行性**：Lite 在自己 tier 下 TTFB / RTF 的 p50/p95 隨句長變化，是否穩定 ≤ 1.5 s / ≤ 0.5？8 kHz mu-law 有無額外延遲？
- **RQ4 批次可行性**：長文（600 / 2,000 字）RTF、輸出上限實際秒數、切段後聲線漂移；Batch API 是否接受 TTS 請求。
- **RQ5 性價比**：Lite 若在 RQ1/RQ2 與 Flash 統計上無顯著差異，三個情境全部用 Lite（省 33%、快 2–3 倍）。

### 4.2 因子
| 因子 | 水準 |
|---|---|
| 模型 | flash, lite |
| 聲線 | Kore/Puck（studio）、tw_female/tw_male（zh-TW 設計 + 台灣腔指示）、ctrl_female/ctrl_male（zh-TW 設計、無口音指示）、cn_female（zh-CN 對照）、(選) rep_tw（複製台灣配音員） |
| style 標註 | 有 / 無 |
| 文本 | 39 句陷阱句（`corpus/traps.jsonl`）+ 3 個情境腳本（虎姑婆睡前故事、手搖飲廣告配音、電信客服） |

完整矩陣 2 × 7 × 2 × 39 ≈ 1,100 段短句（每段 3–8 秒，總成本 < $2），情境腳本另計。

### 4.3 指標
- 客觀：TTFB、wall、RTF、audio tokens/秒、失敗率、截斷、成本。
- 自動粗篩（`judge.py`，gemini-3.8-flash 聽音檔）：口音判定、錯讀清單、標籤是否被唸出字面、CER 近似值。**不是 ground truth**，pilot 顯示它偏寬鬆。
- 人類盲測（`rating/rubric.md`）：≥ 12 位台灣母語者、每人 40 段、隨機化 + 隱藏高低錨；MOS、台灣味 1–5、錯讀字詞、情緒符合度、「可否直接上線」。

### 4.4 通過門檻
- 說故事：MOS ≥ 4.0、台灣味 ≥ 4.0、台語漢字類通過率 ≥ 80%、切段後無可察覺漂移。
- 配音：情緒符合 ≥ 4.0、`<laugh>` 等標籤 100% 被演出。
- 客服：「可上線」≥ 90%、數字/電話/身分證字號 100% 正確、TTFB p95 ≤ 1.5 s、RTF p95 ≤ 0.5。

### 4.5 執行步驟
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...            # 或沿用環境變數 gemini_key

python experiments/make_voices.py                       # 建 5 個設計聲線 → out/voices.json（一次即可，各一年）
python experiments/run_matrix.py traps --models flash,lite --voices Kore,Puck,tw_female,tw_male,ctrl_female,ctrl_male,cn_female
python experiments/run_matrix.py scenarios --models flash,lite --voices Kore,tw_female
python experiments/run_matrix.py cs-realtime --repeat 5                  # 即時：逐句串流
python experiments/run_matrix.py cs-realtime --repeat 5 --telephony      # 8 kHz mu-law
python experiments/bench_latency.py --lengths 20,60,200,600,2000 --repeat 3   # 長度曲線 + 上限
python experiments/judge.py out/traps.jsonl && python experiments/judge.py out/scenarios.jsonl
python experiments/rating/build_listening_test.py out/traps.jsonl out/scenarios.jsonl --raters 12
python experiments/cost.py --hours 100 --calls 1000000 --sec 6
```
輸出全部在 `out/`（git ignore）。盲測用的匿名片段與答案對照表在 `out/listening/`。

### 4.6 已知風險 / 待驗證
- Batch API 對 interactions TTS 的支援（文件互相矛盾）。
- Rate limit 不公開，要用自己的 key 壓測；論壇回報付費 tier 延遲異常。
- 台語漢字讀法不穩；可能需要「台語詞改諧音」的前處理層。
- 語音複製在部分地區不開放，且需要正式同意流程。
- 2027-01-01 價格翻倍，成本模型要用兩個版本算。

---

## 目錄
```
experiments/
  tts_client.py            共用：Interactions API 呼叫、串流 TTFB、WAV、價格常數
  make_voices.py           建立 zh-TW / 對照 設計聲線
  run_matrix.py            traps | scenarios | cs-realtime 三種實驗
  bench_latency.py         TTFB / RTF vs 句長，上限探測
  judge.py                 Gemini 多模態自動評審（粗篩）
  cost.py                  成本試算
  corpus/traps.jsonl       39 句台灣陷阱句（10 類，各附檢查重點）
  corpus/scenarios/        虎姑婆故事、手搖飲廣告配音、電信客服
  rating/rubric.md         人類盲測指引與門檻
  rating/build_listening_test.py  產生匿名化盲測包
  pilot/                   2026-09-25 探測與 pilot 原始數據
```

## 參考
- Google 官方公告：https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-8-text-to-speech/
- 模型卡：https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts 、 https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-lite-tts
- Interactions API TTS 文件：https://ai.google.dev/gemini-api/docs/interactions/speech-generation
- 價格：https://ai.google.dev/gemini-api/docs/pricing
- Cloud TTS 的 Gemini-TTS 頁（有 cmn-TW 代碼、655 s 上限）：https://docs.cloud.google.com/text-to-speech/docs/gemini-tts
- Phil Schmid 實作筆記：https://www.philschmid.de/gemini-3-8-tts
- Simon Willison playground（2,089 聲線、78 秒音檔 20 秒生成）：https://simonwillison.net/2026/Sep/23/gemini-tts-playground/
- 3.1 TTS 串流延遲異常討論：https://discuss.ai.google.dev/t/3-1-flash-tts-preview-streaming-latency/176050
- 台灣媒體：https://technews.tw/2026/09/24/google-unveils-new-gemini-3-8-flash-tts-gemini-3-8-flash-lite-tts-ai-models/ 、 https://www.aiposthub.com/gemini-38-flash-tts-ai-studio/
