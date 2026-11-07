# 深夜 Debug 製作流程（D1 聲線、分段生成、音色匹配）

給下一個要做節目的 agent：照這份從一篇文章做出一集台灣口語的 podcast mp3。
每一步都有指令、產出和通過條件。為什麼這樣做、試過哪些不行，寫在 `RESULTS.md`。

兩人對談、訪問、面試場景用另一份流程：`DIALOGUE_PIPELINE.md`。

這份流程在 2026-11-03 用 EP01 和一個兩段的測試集（`ep00_smoke`）從頭跑過。

## 總覽

| 步驟 | 誰做 | 指令或工具 | 產出 |
|---|---|---|---|
| 0. 環境 | 一次性 | pip、轉換 Breeze | 套件、`/home/user/models/breeze-asr-25-ct2-int8` |
| 1. 草稿與素材 | agent 自己寫 | — | `script/<ep>.json`、`script/sources/<ep>/<段>.txt` |
| 2. 台灣口語改寫 | Gemini 3.8 Flash | `rewrite_episode.py` | `script/<ep>_tw.json` |
| 3. 檢查稿子 | 工具加 agent 逐段核對 | `script_lint.py` | 修正後的 `<ep>_tw.json`，修正紀錄在 `manual_edits` |
| 4. 生成語音 | Gemini 3.8 Flash TTS | `make_podcast.py episode` | 每段三次生成 |
| 5. 挑選 | Breeze-ASR-25 | `select_takes.py` | 每段一個 `<段>.wav` |
| 6. 後製 | ffmpeg | `make_podcast.py master` | `out/podcast/<ep>_tw_D1_<ep>.mp3` |
| 7. 驗收 | Breeze、Gemini、Resemblyzer | `stt_check.py`、`consistency_check.py` | 兩份報告，不合格就回到第 4 或第 3 步 |
| 8. 交付 | — | ffmpeg 寫標籤 | `samples/episodes/` 或交給使用者 |

以下 `<ep>` 是這一集的代號，例如 `ep02`。指令都在 repo 根目錄執行。

## 0. 環境（每個新容器做一次）

需要的環境變數：`gemini_key`（或 `GEMINI_API_KEY`）。

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install --index-url https://download.pytorch.org/whl/cpu torch
python3 -m pip install -r requirements-qa.txt
# 系統的 Pillow 跟 python3.11 不相容時，transformers 會在 import 時出錯：
python3 -m pip install --ignore-installed pillow
# Breeze-ASR-25：從官方權重轉成 CTranslate2 int8（約 3 GB 下載、1.5 GB 結果、幾分鐘）
mkdir -p /home/user/models
ct2-transformers-converter --model MediaTek-Research/Breeze-ASR-25 \
  --output_dir /home/user/models/breeze-asr-25-ct2-int8 --quantization int8 \
  --copy_files tokenizer.json preprocessor_config.json
```

- 一定用 `python3 -m pip`，單打 `pip` 會裝到另一個 Python。
- ffmpeg 已內建。
- 模型放在別的路徑時，設 `BREEZE_CT2=<路徑>`。
- D1 的聲線 ID 在 `results/voices.json`，`make_podcast.py` 會自動讀。

## 1. 草稿與素材（agent 自己寫）

先讀完原文，再把內容切成 8 到 12 段，每段 150 到 350 字。

### `podcast/script/<ep>.json`

```json
{
 "show": "深夜 Debug",
 "episode": "EP02 標題",
 "source": "原文網址",
 "audience": "工程師、想搞懂 AI 的人",
 "segments": [
  {"id": "s00_open", "mood": "開場，輕鬆，像剛按下錄音鍵跟朋友打招呼", "text": "這一段要講的內容（草稿）"},
  {"id": "s01_xxx",  "mood": "輕鬆解說，條理清楚", "text": "…"},
  {"id": "s09_outro", "mood": "收尾，輕鬆溫暖", "text": "…"}
 ]
}
```

- **`id`**：照順序編號，`s00_` 開頭的是開場，最後一個是收尾。
- **`text`**：只決定這段講什麼，不必口語，第 2 步會改寫。事實、人名、數字要對，因為改寫只會更動說法。
- **`mood`**：這段的情緒，會接在語氣指示後面。
  - 不要寫「慵懶」「壓低聲音」「語速偏慢」，會念得畏縮、停頓多。
  - 不要寫「篤定」「句尾俐落」，會變播音腔，台灣人聽起來偏大陸腔。
  - 結尾段的「慢一點」會讓語速明顯變慢，寫了要有心理準備。

### `podcast/script/sources/<ep>/<段落 id>.txt`

每段一個檔，放這段對應的原文摘錄。改寫時事實只能來自這裡，所以摘錄要涵蓋這段要講的全部事實。

範例：`script/ep00_smoke.json` 和 `script/sources/ep00_smoke/`。

## 2. 台灣口語改寫

```bash
python3 podcast/rewrite_episode.py --draft podcast/script/<ep>.json --n 3 --resume
```

- 寫稿 prompt 在 `prompts/spoken_script_zh-TW.md`，規則包括：
  - 每句最多 20 字、每段最多一個精確數字、不條列。
  - 素人感、台灣用字、避開大陸用語。
  - 只有第一段開場、只有最後一段收尾。
- 每段產生三個候選，自動挑沒有大陸用語、口頭禪沒超額、數字少、句子短的那個。
- 整集的口頭禪有額度，例如「你猜」最多 3 次、「我是說」2 次、「醬」2 次，設定在 `rewrite_episode.py` 的 `PHRASE_CAPS`。
- `--resume`：容器重啟會砍掉執行中的工作，加這個會沿用已完成的段落。一段約 1 分鐘。
- 產出：
  - `podcast/script/<ep>_tw.json`
  - 每段的候選和檢查結果在 `podcast/script/rewrites/<ep>_tw/<段>.json`

## 3. 檢查稿子（不能省）

```bash
python3 podcast/script_lint.py podcast/script/<ep>_tw.json
```

通過條件：每段的 `mainland_words` 都是空的，`precise_numbers` 最多一個。

接著 agent 要逐段對照 `sources/<ep>/<段>.txt` 讀一遍，修掉下面這些問題。這些都是實際發生過、自動檢查抓不到的錯：

| 問題 | 實例 | 怎麼改 |
|---|---|---|
| 事實顛倒或誇大 | 「其他評論者說的」寫成「Felix 說的」；「三處不符」寫成「根本對不上」 | 照素材改回 |
| 自己加的數量 | 「遮住部分資料」寫成「蓋住一半」 | 刪掉數量 |
| 改口太多 | 十段裡九段有「我是說」「呃不對」 | 全集留 3 到 4 處 |
| 口頭禪重複 | 「這招，嗯，應該說」出現 6 段 | 換掉或刪掉 |
| 同音或聽起來像別的詞 | 季度→基督、忙人→盲人、正本→這本、時間戳→時間出 | 換說法：每一季的檢討會、一群很忙的人、原文、時間戳記 |
| 偏大陸的網路用語 | 更狠的是、盲猜、坑 | 更扯的是、用猜的、要注意的地方 |
| 書面詞 | 季度、推估、處方 | 換成聊天的說法 |

改完把每一處記在 `podcast/script/rewrites/<ep>_tw/<段>.json` 的 `manual_edits`，格式是 `{"from": …, "to": …, "reason": …}`，再存回 `<ep>_tw.json`。

## 4. 生成語音

```bash
python3 podcast/make_podcast.py episode --voice D1 --script podcast/script/<ep>_tw.json \
  --tag <ep> --style v5 --takes 3
```

- **D1** 是設計聲線 `voice_b3c8x0jsntqc`，閒置一年才會刪除，使用會延長效期。每隔幾個月要用它生成一次。
- **語氣 v5** 在 `styles.json`：台灣華語特色、素人感，加上「聲調要清楚」。v4 把四聲念平，「季度」被聽成「基督」。
- **每段念三次**：Gemini TTS 沒有種子，每次生成差很多，例如同一段的長停頓可能是 4 次，也可能是 15 次。
- **時長檢查**：每次生成都會自動檢查時長，太短或太長就重念，最多重試 2 次。
- **中斷續跑**：已存在的生成檔不會重做，中斷後重下同一指令即可。
- 一集約 30 次請求、8 到 10 分鐘，費用約 0.35 美元（2027 年起加倍）。

## 5. 挑選

```bash
python3 podcast/select_takes.py --script podcast/script/<ep>_tw.json --segments out/podcast/segments/D1_<ep> \
  --asr breeze --consistency --neighbour
```

依序篩選：

1. **清楚**：Breeze 盲聽錯誤率跟最好的那次差 0.012 以內。
2. **像同一個人**：聲紋接近整集平均，差 0.015 以內。
3. **亮暗接近**：音色重心離整集中位數最近的那次再加 300 Hz 以內。
4. **停頓**：長停頓最少。

最後再跑一輪相鄰段比對：如果有一次生成跟前後段更像，相似度高出 0.01 以上，就換成那次。

- 選擇紀錄在 `out/podcast/segments/D1_<ep>/select_log.json`。
- Breeze 在 CPU 上轉寫 30 次生成大約要 20 分鐘。
- 只改規則時加 `--reuse`，會沿用之前的轉寫，只轉寫新的生成。

## 6. 後製

```bash
python3 podcast/make_podcast.py master --voice D1 --tag <ep> --script podcast/script/<ep>_tw.json --match-eq
```

1. 每段先調到 -20 LUFS。各段分開生成，音量會差 4 到 6 dB。
2. `--match-eq` 做音色匹配：每段的頻譜往整集中位數拉 80%，每個頻帶最多 ±6 dB，再把音量調回 -20 LUFS。
3. 接上程式合成的片頭片尾和 0.6 秒段間停頓。
4. 整集處理：高通、壓縮，再正規化到 -16 LUFS，輸出 128 kbps 單聲道 mp3。

產出：

- `out/podcast/<ep>_tw_D1_<ep>.mp3`
- 每段處理後的音檔、`levels.json`、`match_eq.json` 在 `out/podcast/master/norm_D1_<ep>/`

## 7. 驗收

```bash
python3 podcast/stt_check.py --asr breeze --script podcast/script/<ep>_tw.json \
  --segments out/podcast/segments/D1_<ep> --out podcast/results/<ep>/stt_check.json
python3 podcast/consistency_check.py --script podcast/script/<ep>_tw.json \
  --segments out/podcast/master/norm_D1_<ep> --out podcast/results/<ep>/consistency.json
```

通過條件：

| 檢查 | 通過 | EP01 的實際值 |
|---|---|---|
| Breeze 盲聽錯誤率，各段平均 | 3.5% 以下 | 3.0% |
| 兩套辨識都聽錯的內容詞 | 0 處 | 1 處，是「掰掰」寫成「拜拜」，不算 |
| `consistency_check.py` | 全部段落在範圍內 | 全部通過 |

讀 `stt_check.py` 的標記要注意：

- **兩邊都錯**：念不清楚或用字有問題。回第 3 步改稿，或回第 4 步重念。
- **只有 Breeze 標**：Breeze 常把英文詞拼錯，例如 Claude、Three.js；中文內容詞要到標註的時間點聽一下。
- **只有 Gemini 標**：Gemini 常把「二零二六」聽成「二零二四」，這是辨識端的偏差。

一致性不合格（跟上一段不像、音高、亮暗或響度偏離）時，替那一段補生成，再挑選和後製：

```bash
python3 podcast/make_podcast.py episode --voice D1 --script podcast/script/<ep>_tw.json --tag <ep> --style v5 \
  --only <段落 id> --add-takes 3
python3 podcast/select_takes.py --script podcast/script/<ep>_tw.json --segments out/podcast/segments/D1_<ep> \
  --asr breeze --consistency --neighbour --reuse
python3 podcast/make_podcast.py master --voice D1 --tag <ep> --script podcast/script/<ep>_tw.json --match-eq
```

`--add-takes` 只會新增生成，不動原本的。

不要用 `qa_episode.py` 驗收清晰度：它把原稿給評審，評審會照稿「聽出」字，抓不到念不清楚的地方。

## 8. 交付

```bash
ffmpeg -y -loglevel error -i out/podcast/<ep>_tw_D1_<ep>.mp3 -map_metadata -1 -c copy \
  -metadata title="<集數與標題>" -metadata artist="深夜 Debug" -metadata album="深夜 Debug" \
  -metadata comment="Synthetic voice generated by TTS; source <原文網址>" \
  podcast/samples/episodes/<ep>-tw_gemini-3.8-flash_d1_style-v5.mp3
```

把 `stt_check.json`、`consistency.json`、`select_log.json`、`match_eq.json` 放進 `podcast/results/<ep>/`，跟 mp3 一起提交。

## 不要做的事

- 不要讓 Gemini 評審判斷台灣口音：它把使用者覺得偏大陸腔的版本排成最台灣。口音只能請台灣母語者聽。
- 不要複製或模仿真人的聲音，包括知名主持人；聲音複製必須是本人錄同意句。
- 不要把稿子寫成一句一行：TTS 會在每個換行停頓。
- 不要只看清晰度挑選：會挑到停頓很多的版本。
- 不要加重壓縮：會把氣音和齒音放大，聲音變亮。

## 時間與費用（一集約 9 分鐘、2,400 字）

| 步驟 | 時間 | 費用（2026 年底前） |
|---|---|---|
| 2. 改寫，10 段各 3 候選 | 約 10 分鐘 | 約 0.36 美元 |
| 4. 生成，30 次 | 約 8 到 10 分鐘 | 約 0.35 美元 |
| 5. 挑選，Breeze 本機 | 約 20 分鐘 | 0 |
| 6. 後製 | 約 2 分鐘 | 0 |
| 7. 驗收，Breeze 加 Gemini 盲聽 | 約 10 分鐘 | 約 0.06 美元 |
| 合計 | 約 50 分鐘 | 約 0.8 美元，2027 年起約 1.6 美元 |

加上第 1、3 步 agent 自己的寫稿和核對時間。

## 替代方案

- **整集一次生成**：10 分鐘以內可以，聲音較連貫，但音色仍會漂，也沒辦法逐段重念。
- **ElevenLabs Hardy**：最清楚，但長停頓是 D1 的兩倍，免費方案字元額度有限。用法見 `elevenlabs_tts.py episode --voice HARDY`。

兩者的數據都在 `RESULTS.md`。
