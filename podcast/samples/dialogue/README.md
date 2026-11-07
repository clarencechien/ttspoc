# 對談測試：技術面試場景

全部都是 TTS 合成的聲音，沒有真人錄音，也沒有複製任何真人的聲音。
稿子來源：〈哪條線接得通（修訂）〉 https://imitator.ai-apps.work/r/claude-sessions
稿子：`podcast/dialogue/interview_claude_sessions.json`（23 輪、約 590 字）。
生成日期：2026-11-07。

設定：女面試官要有威嚴（句子短、追問、會打斷），男面試者要有不確定感（呃、停頓、講錯再改口）。
三個版本用同一份稿，差別在生成方式。

| 檔案 | 生成方式 | 聲線 | 長度 |
|---|---|---|---|
| `interview_A_gemini-multi_designed-voices_patched.mp3` | **A**：Gemini 多人模式，整段一次請求，附和用 `\|嗯\|` 讓模型自己生 | 設計聲線 IV_F（面試官）、IV_M（面試者） | 2:31 |
| `interview_A-raw_gemini-multi_kore-achird_voice-swaps.mp3` | A 的對照：內建聲線、沒修過，**保留換錯人的地方** | 內建 Kore（女）、Achird（男） | 2:32 |
| `interview_B_gemini-per-turn_spliced.mp3` | **B**：Gemini 一輪一次請求，再用剪接做出附和和搶話 | IV_F、IV_M | 2:23 |
| `interview_C_elevenlabs-v3_ling-james.mp3` | **C**：ElevenLabs Text to Dialogue（`eleven_v3`），整段一次請求 | 聲音庫的台灣聲音 Ling（女）、James（男） | 2:05 |
| `design-preview_IV_F_interviewer.mp3`、`design-preview_IV_M_candidate.mp3` | 設計聲線時 API 回傳的試聽片段 | | |

可以注意聽的地方：
- A-raw 0:32「那你電腦關掉呢？」和 1:16「cloud 做的是什麼？」是面試官的台詞，卻是男聲念的。
- A 修補版 0:29 那句是從 B 剪過來補上的。
- B 的附和在 0:18、0:46、1:39、2:07，是面試官的「嗯」疊在面試者講話的停頓下面。
- B 的搶話在 1:11 左右：面試官提早 0.35 秒開口，面試者的尾巴同時淡出。

## 第二場：一百萬則通知（D1 當面試官）

稿子來源：〈你連的是什麼線〉 https://imitator.ai-apps.work/r/which-wire
稿子：`podcast/dialogue/interview_which_wire.json`（23 輪）。
資深架構師連續追問「Black Friday 午夜送一百萬則通知」，面試者從背標準答案，到被問出漏洞。

| 檔案 | 生成方式 | 聲線 | 長度 |
|---|---|---|---|
| `interview2_which-wire_B_gemini-per-turn_d1-interviewer.mp3` | B 的做法：逐輪生成＋剪接；說錯的輪次單獨重生 3 次，挑最清楚的 | 面試官 D1（磁性深夜）、面試者 IV_M（跟第一場同一個人） | 2:40 |
| `interview2_which-wire_B_gemini-per-turn_d1-v5-interviewer.mp3` | 同上，面試官加上 `base_style: v5`（podcast 的 D1 語氣），稿子 `interview_which_wire_d1v5.json`；面試者的輪次直接沿用上一版 | D1 + v5、IV_M | 2:37 |

- 附和在 0:27、1:12（v5 版在 0:26、1:10），是面試官的「嗯」。
- 搶話在 1:41（v5 版 1:40）：面試官接「只會多拿到一堆 429」。
- v5 版第 16 輪把「冪等」改成「防重複送」：v5 的懶音把「冪等」念糊了，Breeze 和 Gemini 都聽成 meet / meter。

`d1-compare_reference_interview-style_vs_podcast-v5.mp3`（1:14）：D1 聽起來跟 podcast 不一樣，用這個檔對照。
1. 先播 D1 的參考錄音（podcast 時期）。
2. 接著三組台詞：開場、「推播之後湧進來的那一波」、收尾。每組先播面試版（架構師 persona），再播同一句改用 podcast v5 語氣。

## 聲線

| 代號 | 服務 | ID | 描述 |
|---|---|---|---|
| IV_F | Gemini 設計聲線 | `voice_u3fnij37psh2` | 四十出頭的台灣女性技術主管，中低音，沉穩有威嚴，冷靜克制 |
| IV_M | Gemini 設計聲線 | `voice_ctrzzph70vfc` | 二十七、八歲的台灣男工程師，中音、乾淨、偏年輕 |
| D1 | Gemini 設計聲線 | `voice_b3c8x0jsntqc` | podcast 的主持人聲線，第二場拿來當面試官 |
| Ling | ElevenLabs 聲音庫 | `Z8Aisvg1z70p27kGvkZZ` | cmn-TW，middle_aged，steady / calm / grounded |
| James | ElevenLabs 聲音庫 | `UwT0JPexcCbH107hq7i5` | cmn-TW，young，friendly |

IV_F 和 IV_M 也登錄在 `podcast/results/voices.json`，效期一年，有使用就會延長。

## 重現

```bash
python podcast/make_dialogue.py design        # 已建立就跳過
python podcast/make_dialogue.py gemini-multi --voices I=IV_F,C=IV_M --name A_gemini-multi_designed
python podcast/make_dialogue.py gemini-turns --voices I=IV_F,C=IV_M --name B_gemini-turns_designed
python podcast/make_dialogue.py elevenlabs --voices I=Z8Aisvg1z70p27kGvkZZ,C=UwT0JPexcCbH107hq7i5 --name C_elevenlabs-v3_ling-james
python podcast/dialogue_qa.py out/dialogue/*.wav           # Breeze 盲測 CER + 用音高檢查有沒有換錯人
python podcast/make_dialogue.py patch out/dialogue/A_gemini-multi_designed.wav out/dialogue/A_fixed.wav \
    --start 28.85 --end 30.2 --clip out/dialogue/B_gemini-turns_designed/turn_04.wav
python podcast/make_dialogue.py master out/dialogue/<name>.wav podcast/samples/dialogue/<name>.mp3

# 第二場：D1 當面試官；QA 標出的輪次重生後重新組裝
python podcast/make_dialogue.py gemini-turns --script podcast/dialogue/interview_which_wire.json --voices I=D1,C=IV_M --name B_which-wire_d1-ivm
python podcast/dialogue_qa.py out/dialogue/B_which-wire_d1-ivm.wav --script podcast/dialogue/interview_which_wire.json
python podcast/retake_turns.py --script podcast/dialogue/interview_which_wire.json --voices I=D1,C=IV_M --name B_which-wire_d1-ivm --turns 0,6,8 --takes 3
python podcast/make_dialogue.py gemini-turns --script podcast/dialogue/interview_which_wire.json --voices I=D1,C=IV_M --name B_which-wire_d1-ivm
```

Gemini 沒有種子參數，重跑出來的聲音表現會不一樣，A 換錯人的位置也會不一樣。ElevenLabs 固定 `seed=7`，送出的請求存在 `podcast/results/dialogue/`。
結果與數據見 `podcast/RESULTS.md` 的「對談：面試場景」一節。
