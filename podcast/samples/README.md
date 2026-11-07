# 深夜 Debug 音檔

全部都是 TTS 合成的聲音，沒有真人錄音，也沒有複製任何真人的聲音。
稿子來源：〈記住了第一招，漏掉了第五招〉 https://imitator.ai-apps.work/r/fifth-move
生成日期：2026-11-03。

檔名規則：`{用途}_{服務商}-{模型}_{聲線}.{副檔名}`。設計聲線用代號（d1、el1），內建聲線用名稱（enceladus）。

## episodes/：完整一集
同一份稿 `podcast/script/ep01.json`，三個版本。

| 檔案 | 服務商與模型 | 聲線 | 長度 | 比較式排名 |
|---|---|---|---|---|
| `ep01_gemini-3.8-flash_enceladus.mp3` | Gemini `gemini-3.8-flash-tts` | 內建 Enceladus | 8:11 | 第 1 |
| `ep01_gemini-3.8-flash_d1-magnetic-night.mp3` | Gemini `gemini-3.8-flash-tts` | 設計聲線 D1 磁性深夜 | 8:30 | 第 2 |
| `ep01_elevenlabs-v4_el1.mp3` | ElevenLabs `eleven_v4` | 設計聲線 EL1 | 7:14 | 第 3 |
| `ep01-tw_gemini-3.8-flash_d1_style-v4.mp3` | Gemini `gemini-3.8-flash-tts` | D1，台灣口語稿 `ep01_tw.json` + v4 語氣 | 8:29 | 尚未排名 |
| `ep01-tw_elevenlabs-v4_el1_tw-tag.mp3` | ElevenLabs `eleven_v4` | EL1，同一份台灣口語稿，段首加台灣口音標籤 | 7:44 | 尚未排名 |
| `ep01-tw_gemini-3.8-flash_d1_style-v5_clarity.mp3` | Gemini `gemini-3.8-flash-tts` | D1，改過易混詞的台灣口語稿 + v5 語氣，依清晰度與一致性挑選，逐段響度與音色匹配 | 8:31 | 尚未排名 |
| `ep01-tw_elevenlabs-v4_hardy.mp3` | ElevenLabs `eleven_v4` | 聲音庫的台灣聲音 Hardy，同一份改過的稿，每段一次 | 8:29 | 尚未排名 |
| `ep01-tw_gemini-3.8-flash_d1_style-v5_single-request.mp3` | Gemini `gemini-3.8-flash-tts` | D1 + v5，整集一次生成，沒有片頭片尾 | 8:11 | 尚未排名 |

- 三集都是 128 kbps 單聲道 mp3，響度約 -16.7 LUFS，片頭片尾是程式合成的短音效。
- 排名、逐段校對與成本在 `podcast/RESULTS.md`。

## dialogue/：對談測試（面試場景）
女面試官、男面試者，2～3 分鐘，三種做法：Gemini 多人一次請求、Gemini 逐輪加剪接、ElevenLabs Text to Dialogue。說明在 `dialogue/README.md`。

## auditions/：試聽
每個候選聲線念同一句試聽稿（`ep01.json` 的 `audition_text`），用來選聲。

| 檔案 | 說明 |
|---|---|
| `gemini-3.8-flash_{enceladus,charon,algieba,umbriel}.mp3` | Gemini 內建聲線，第一輪選聲 |
| `gemini-3.8-flash_{d1-magnetic-night,d2-engineer-senior}.mp3` | Gemini 設計聲線，第一輪選聲 |
| `elevenlabs-v3_el{0,1,2}.mp3`、`elevenlabs-v4_el{0,1,2}.mp3` | ElevenLabs 三個設計聲線，各用 v3 和 v4 念 |
| `gemini-3.8-flash_{enceladus,d1-magnetic-night}_run2.mp3` | ElevenLabs 對照那輪重新生成的 Gemini 基準，排名用的是這兩段 |

## references/：參考錄音
每個聲線保存一段參考錄音，作為「這個聲音原本長什麼樣」的依據。換模型或聲線過期時，用 `podcast/match_voice.py` 拿新候選跟這裡比對，挑最接近的。

- Gemini 的參考錄音是 FLAC 無損格式。ElevenLabs 只有 96 kbps mp3，因為原始 wav 在另一個 session。
- `references.json` 記錄每段的模型、聲線名稱或 ID、生成參數、到期日、音高中位數、SHA-256，以及聲紋向量。

| 聲線 | 模型 | 聲線名稱或 ID | 到期 |
|---|---|---|---|
| Enceladus | `gemini-3.8-flash-tts` | `Enceladus` | 隨模型下架 |
| Charon、Algieba、Umbriel | `gemini-3.8-flash-tts` | 同名 | 隨模型下架 |
| D1 磁性深夜 | `gemini-3.8-flash-tts` | `voice_b3c8x0jsntqc` | 閒置一年後；2026-11-04 顯示 2027-11-04 |
| D2 工程師學長 | `gemini-3.8-flash-tts` | `voice_e51ofjtjia55` | 閒置一年後，目前顯示 2027-11-03 |
| EL0 | `eleven_v4` | `NgphutLJuu0MWBHCgcXK` | 不會自動過期 |
| EL1 | `eleven_v4` | `75JywuJ8Qm0zEIhLabLL` | 不會自動過期 |
| EL2 | `eleven_v4` | `VWBBlPIiQsGsFmdcqUAz` | 不會自動過期 |

要重現聲音，必須同時固定聲線和模型：
- **Gemini 內建聲線**：同一個模型內聲音一致。換模型後名稱還在，但聲音會漂移，見 `model-drift/`。
- **Gemini 設計聲線**：閒置一年才會過期。拿來合成或當作 `base_voice` 會延長效期，但大約每天批次更新一次，不是即時。2026-11-04 實測：D1 前一天持續使用，效期從 2027-11-03 延到 2027-11-04；之後沒再用的 D2 維持原效期。沒有種子參數，過期後無法做出一模一樣的聲音，只能用下面的方法做出相近的聲音。

### D1 重現測試（2026-11-03）
同一句試聽稿，跟 D1 的參考錄音比聲紋相似度：

| 方法 | 相似度 |
|---|---|
| 原本的 D1 再念三次 | 0.95 |
| 以 D1 為 `base_voice` 做 remix，描述寫「完全不要改變」 | 0.93 |
| 用一模一樣的描述重新設計，兩次 | 0.89–0.91 |
| 其他聲線（Enceladus、Charon） | 0.74–0.77 |

- remix 最接近，但不是同一個聲音。它要在 D1 還存在時才能做，可以當作備份聲線。
- 重新設計會落在相近的音域和口音，但每次都不同，要多做幾個再用 `match_voice.py` 挑最接近的。
- 測試建立的聲線已刪除。
- **ElevenLabs 設計聲線**：存在帳號裡不會過期。設計時固定了 seed 20261103，同 seed 加同描述可以重新設計出同一個聲音。同一個聲線 ID 換用 v3 或 v4，聲音也會不同。

## design-previews/：聲線設計預覽
建立設計聲線時服務商回傳的預覽音檔，內容由服務商決定。

| 檔案 | 說明 |
|---|---|
| `gemini_d1-magnetic-night.mp3`、`gemini_d2-engineer-senior.mp3` | Gemini 設計聲線的預覽 |
| `elevenlabs_el{0,1,2}.mp3` | ElevenLabs Voice Design 的三個預覽，念的是 `elevenlabs_tts.py` 的 `PREVIEW_TEXT` |

## model-drift/：同一個名稱，不同代模型
同一句話、同樣用 Enceladus，在四代 Gemini TTS 生成，加上一段換成 Charon 的對照。

| 檔案 | 模型 | 模型發布 |
|---|---|---|
| `enceladus_gemini-3.8-flash.mp3` | `gemini-3.8-flash-tts` | 2026-09 |
| `enceladus_gemini-3.1-flash-preview.mp3` | `gemini-3.1-flash-tts-preview` | 2026-02 |
| `enceladus_gemini-2.5-pro-preview.mp3` | `gemini-2.5-pro-preview-tts` | 2025-05 |
| `enceladus_gemini-2.5-flash-preview.mp3` | `gemini-2.5-flash-preview-tts` | 2025-05 |
| `control_charon_gemini-3.8-flash.mp3` | `gemini-3.8-flash-tts` | 對照組 |

每個模型各生成三次後，與 3.8 Flash 的 Enceladus 比較的平均聲紋相似度：

| 比較對象 | 聲紋相似度 |
|---|---|
| 3.8 Flash 自己三次互比 | 0.93 |
| 3.1 Flash preview | 0.90 |
| 3.8 Flash-Lite | 0.89 |
| 2.5 Pro preview | 0.87 |
| 2.5 Flash preview | 0.83 |
| 換成 Charon | 0.79–0.81 |

- 聲紋模型是 Resemblyzer，用英文訓練，每個模型只測一句、三次，所以只能看趨勢。
- 2.5 與 3.1 的 TTS 模型最早可能在 2026-11-17 下架；3.8 目前沒有公布下架日期。

## script-rewrite/：稿子口語化與語氣調整
第五招加行星案例那一段，全部用 D1 系列聲線，響度統一為 -16 LUFS，方便公平比較。

| 檔案 | 稿子 | 語氣 | 聲線與後製 |
|---|---|---|---|
| `s05_v1_old-script_old-style_d1.mp3` | 原稿 | v1 慵懶偏慢 | D1 |
| `s05_v2_new-script_old-style_d1.mp3` | 改寫稿，一句一行 | v1 | D1 |
| `s05_v3_new-script_new-style_d1.mp3` | 改寫稿，段落排版 | v2 自信有節奏 | D1，自動盲評第一，但真人聽起來偏大陸腔 |
| `s05_v4_new-script_new-style_d1_warm-eq.mp3` | 同 v3 | v2 | D1 加溫和等化 eqA，較厚較暖 |
| `s05_v5_new-script_new-style_d1-remix-raspy.mp3` | 同 v3 | v2 | D1 remix「沙啞電台」D1M2 |
| `s05_v6_new-script_new-style_d1-remix-confident.mp3` | 同 v3 | v2 | D1 remix「磁性自信」D1M1 |
| `s05_v7_new-script_tw-style_d1_take1.mp3` 到 `take3` | 改寫稿，段落排版 | v3 台灣口音優先、有節奏 | D1，念三次；第 1 次停頓最少 |
| `s05_v8_old-script_tw-phonetic-style_d1.mp3` | 改寫稿，段落排版 | v4 寫明台灣華語發音特色、素人感 | D1 |
| `s05_v9_casual-script_tw-phonetic-style_d1_take1.mp3`、`take2` | 素人稿，台灣口語用字 | v4 | D1，念兩次；第 2 次最快、沒有長停頓 |

真人試聽：v2 最台灣，v3、v4 偏大陸腔；Gemini 評審的口音排名正好相反，口音以真人判斷為準。
數據與結論在 `podcast/RESULTS.md` 的「稿子口語化與 D1 語氣調整」。

## el-tune/：ElevenLabs 調整（第七段）
同一段台灣口語稿，響度統一為 -16 LUFS。

| 檔案 | 設定 |
|---|---|
| `s06_gemini-3.8-flash_d1_style-v4.mp3` | Gemini 對照，取自整集 |
| `s06_elevenlabs-v4_el1_a-default.mp3` | EL1，穩定度 0.5、風格 0.3 |
| `s06_elevenlabs-v4_el1_b-expressive.mp3` | EL1，穩定度 0.35、風格 0.5 |
| `s06_elevenlabs-v4_el1_c-tw-tag.mp3` | EL1，預設設定，段首加 `[Taiwanese accent] [casually]`，整集採用 |

## el-library/：ElevenLabs 聲音庫的台灣男聲
同一段 74 字，eleven_v4，預設設定；EL1 那段另加台灣口音標籤。響度統一為 -16 LUFS。

| 檔案 | 聲音 | 音高 |
|---|---|---|
| `elevenlabs-v4_evan.mp3` | Evan，溫暖、放鬆 | 118 Hz |
| `elevenlabs-v4_akun.mp3` | Akun，溫暖、有磁性 | 123 Hz |
| `elevenlabs-v4_neil-chuang.mp3` | Neil Chuang，低沉、可信賴 | 131 Hz |
| `elevenlabs-v4_jerry-lin.mp3` | Jerry Lin，低沉、沉穩 | 132 Hz |
| `elevenlabs-v4_hardy.mp3` | Hardy，台灣大叔 | 140 Hz |
| `elevenlabs-v4_zack.mp3` | Zack，柔和、適合 podcast | 142 Hz |
| `elevenlabs-v4_el1-tw-tag.mp3` | EL1，自己設計的聲線 | 148 Hz |
