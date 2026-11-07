# 對談製作流程（兩人對話、逐輪生成、剪接附和與搶話）

給下一個要做對談、訪問或面試場景的 agent：照這份流程，從一篇文章做出一段 2～3 分鐘、台灣口語的兩人對話 mp3。
做法是 B：每一輪各自用 Gemini 3.8 Flash TTS 生成，附和和搶話用剪接做。說錯哪一句，就只重生那一句。
為什麼選 B、另外兩種做法（Gemini 多人模式一次生成、ElevenLabs Text to Dialogue）哪裡不行，寫在 `RESULTS.md` 的「對談：面試場景」一節。

這份流程在 2026-11-07 跑過兩場：
- `interview_claude_sessions`：女面試官 IV_F、男面試者 IV_M。
- `interview_which_wire`：面試官 D1、面試者 IV_M。

單人 podcast 的流程是另一份，見 `PIPELINE.md`。

## 總覽

| 步驟 | 誰做 | 指令或工具 | 產出 |
|---|---|---|---|
| 0. 環境 | 一次性 | 同 `PIPELINE.md` 第 0 步，加 twtonepoc | 套件、Breeze、`twtone` |
| 1. 寫稿 | agent 自己寫 | — | `podcast/dialogue/<scene>.json` |
| 2. 檢查稿子 | 工具加 agent 核對 | `script_lint.py`、`twtone` | 修正後的稿子 |
| 3. 選聲線 | agent | `make_dialogue.py design`（需要新聲線時） | 兩個聲線代號 |
| 4. 逐輪生成與組裝 | Gemini 3.8 Flash TTS | `make_dialogue.py gemini-turns` | `out/dialogue/<name>/turn_XX.wav`、`out/dialogue/<name>.wav` |
| 5. 驗收 | Breeze-ASR-25 | `dialogue_qa.py` | 錯字和它在第幾輪 |
| 6. 重生有錯的輪次 | Gemini TTS + Breeze | `retake_turns.py`，必要時改稿加上 `--redo` | 每輪挑最清楚的版本 |
| 7. 重新組裝、試聽、後製 | ffmpeg、Gemini | `gemini-turns`（用快取）、`master` | `podcast/samples/dialogue/<name>.mp3` |
| 8. 交付 | — | — | README、RESULTS、commit |

以下 `<scene>` 是稿子檔名，例如 `interview_which_wire`。`<name>` 是這次生成的代號，例如 `B_which-wire_d1-ivm`。指令都在 repo 根目錄執行。

## 0. 環境

1. 照 `PIPELINE.md` 第 0 步裝套件、轉 Breeze-ASR-25。需要的環境變數是 `gemini_key`。
2. 檢查台灣用語要用 twtonepoc：

```bash
git clone --depth 1 https://github.com/clarencechien/twtonepoc /home/user/clarencechien/twtonepoc
# 第一次執行會自動下載 zhtw-mcp 預編 binary
```

## 1. 寫稿：`podcast/dialogue/<scene>.json`

```json
{
 "title": "面試：…", "source": "<原文網址>",
 "speakers": {
  "I": {"name": "面試官", "gender": "male", "persona": "…", "base_style": "v5"},
  "C": {"name": "面試者", "gender": "male", "persona": "…"}
 },
 "turns": [
  {"speaker": "I", "style": "這一句怎麼演", "text": "台詞"},
  {"speaker": "C", "style": "…", "text": "呃，前面放一個 queue，[[嗯]]後面一組 worker…"},
  {"speaker": "I", "style": "…", "gap": 0.8, "text": "…"},
  {"speaker": "C", "style": "…最後一句還沒講完就被打斷", "text": "所以開再多 worker——"},
  {"speaker": "I", "style": "直接接話打斷", "overlap": 0.3, "text": "只會多拿到一堆 429。"}
 ]
}
```

欄位說明：
- `persona`：這個人是誰、怎麼講話，每一輪都會帶上。
- `base_style`（可省略）：
  - 放 `styles.json` 的代號，例如 `v5`，或直接寫一段文字。
  - 這段會放在 persona 前面。
  - 想讓聲線保留原本的樣子，例如 D1 要聽起來像 podcast 主持人，就加上它（見第 3 步）。
- `style`：這一句的演法，例如「愣住，停一拍，慢慢想通」。
- `[[嗯]]`：**聽的那一方**在這裡附和，會疊在說話者最近的停頓下面。
  - 只放在對方講比較長的輪次裡，而且要在逗號或子句之間。
  - 一場放 2～4 個就夠。
- `gap`：這一輪開口前的靜音秒數，預設 0.35。
  - 追問用 0.2～0.3。
  - 換題、施壓、想事情用 0.7～0.9。
- `overlap`：這一輪提早幾秒開口，壓在上一輪的尾巴上，用來做搶話，建議 0.3～0.35。
  - 上一輪的台詞要以「——」結尾，style 寫「還沒講完就被打斷」。
  - 被打斷的那一輪會在 0.25 秒後淡出。

寫稿規則：
- **長度**：約 450～600 個漢字、20～24 輪，大約 2.5 分鐘。
- **事實**：每個技術說法都要能在原文找到。寫完逐句對照原文。
- **台灣口語**：
  - 規則跟 `prompts/spoken_script_zh-TW.md` 一樣，不要有大陸用語。
  - 「打掛」「沒差」「客訴」這類台灣口語可以用。
- **指令和英文要寫成念法**：
  - `/rc` 寫成「slash RC」，`--teleport` 寫成「teleport」，`claude -p` 寫成「claude dash p」，`429` 照寫。
  - 數字用中文寫，例如「一千個」「一百萬則」。
- **角色要有反差**：
  - 強勢的一方：句子短、問完就停、不幫對方圓場。
  - 弱勢的一方：呃、停頓、講錯再改口，答對時語氣才慢慢穩下來。
  - 最後讓弱勢的一方有一句講對的話，收尾才有層次。
- **不要寫「不是 A，是 B」**：twtone 會抓，這是最強的 AI 寫作特徵。改成「A 之後的 B，才會…」這類句型。

## 2. 檢查稿子

```bash
S=<scratchpad>
python3 -c "
import json,re
d=json.load(open('podcast/dialogue/<scene>.json'))
t=[re.sub(r'\[\[.*?\]\]','',x['text']) for x in d['turns']]
open('$S/s.txt','w').write('\n'.join(t))
open('$S/s.md','w').write('# 稿\n\n'+'\n\n'.join(d['speakers'][x['speaker']]['name']+'：'+y for x,y in zip(d['turns'],t))+'\n')"
python3 podcast/script_lint.py $S/s.txt                       # mainland_words 要是 []
(cd /home/user/clarencechien/twtonepoc && ./twtone $S/s.md --full)
```

通過條件：
- `script_lint` 的 `mainland_words` 是空的。
- zhtw-mcp 沒有用詞錯誤。
- twtone 的「對舉」要改掉。
- 下面這些是故意寫的，可以保留：
  - 頓號連排：角色在背答案。
  - 破折號：被打斷。
  - 「重複」：例如「不行，不行」。

## 3. 選聲線

已建立、可以直接用的 Gemini 設計聲線（ID 在 `podcast/results/voices.json`，閒置一年才過期，有使用就延長）：

| 代號 | 性別 | 適合 |
|---|---|---|
| D1 | 男，低沉磁性（podcast 主持人） | 主持人、資深的一方 |
| IV_F | 女，四十出頭技術主管，中低音、冷靜 | 面試官、主管 |
| IV_M | 男，二十七、八歲工程師，中音、偏年輕 | 面試者、來賓 |
| D2 | 男，三十歲工程師學長 | 備用 |

- 也可以用 Gemini 內建聲線（例如 Kore、Achird），直接寫名字就好。
- 需要新聲線時，在 `make_dialogue.py` 的 `DESIGNS` 加一筆，再跑 `python3 podcast/make_dialogue.py design`（已存在的會跳過）。
- 兩個都是同性別時，音高要差 20 Hz 以上，persona 也要拉開，例如年紀、語速。D1 是 93 Hz，IV_M 是 118 Hz。

**persona 會改變聲線聽起來的樣子。**
- 同一個 D1，在 podcast 用 v5 語氣（素人、懶音、聊天），在面試用「資深架構師、慢、有份量」。
- 聲紋相似度 0.976，量起來是同一個聲音。
- 但聽起來像換了一個人，演得重的幾句跟參考錄音只剩 0.73～0.83。
- 要讓聽眾認得出是同一位主持人，就加上 `"base_style": "v5"`，persona 只寫角色，不要再描述音色。

對照檔：`samples/dialogue/d1-compare_reference_interview-style_vs_podcast-v5.mp3`。

## 4. 逐輪生成與組裝

```bash
python3 podcast/make_dialogue.py gemini-turns --script podcast/dialogue/<scene>.json \
    --voices I=D1,C=IV_M --name <name>
```

這一步會做這些事：
- 每一輪一次請求，存成 `out/dialogue/<name>/turn_XX.wav`。已經存在的檔案會跳過，所以重跑等於重新組裝。
- 每輪生成完會檢查「單一取樣點的跳動」。超過 0.7（`CLICK`）就是 Gemini 輸出的爆音，會自動重生，最多 3 次；被擋下的放在 `rejected/`。
- 附和：聽的那一方念「嗯」3 次，挑最短、乾淨的，用有聲音部分的 RMS 對齊，比說話者小 7 dB（`--bc-db`）。
- 每一輪先去掉頭尾靜音，加 15 ms 淡入淡出，響度統一到 -20 LUFS（`--turn-lufs`），再照 `gap`、`overlap` 排進時間軸。
- 時間軸和附和的位置寫在 `out/dialogue/<name>/timeline.json`。

## 5. 驗收

```bash
python3 podcast/dialogue_qa.py out/dialogue/<name>.wav --script podcast/dialogue/<scene>.json \
    --out out/dialogue/qa_<name>.json
```

- 輸出 Breeze 盲測的 CER、聽起來不一樣的錯字（帶聲調比對），以及每個錯字在第幾輪（`turns with misses`）。
- 一男一女時，還會用每輪的音高檢查有沒有給錯聲線。同性別時這項自動跳過。

這些是 Breeze 自己轉寫的問題，**不用重生**：
- 「queue」被漏掉、寫成 Q。
- 數字被寫成阿拉伯數字，例如「一千」變成 1000。
- 「Claude」寫成 cloud、「call」寫成 code。
- 「不通」變成「不同」。
- 「得 / 的」。
- 前後鼻音不分，例如「深 → 生」。這本來就是台灣口音。

其他的錯字都算真的念錯，例如 坐→左、逐→主、擊→接、客訴→剋屬、擱置→革職。

## 6. 重生有錯的輪次

```bash
python3 podcast/retake_turns.py --script podcast/dialogue/<scene>.json --voices I=D1,C=IV_M \
    --name <name> --turns 0,8,11 --takes 3
```

- 把目前的版本加上 3 個新版本，每個版本單獨給 Breeze 聽。
- 排序依序是：沒有爆音優先、真正的錯字最少、CER 最低。最好的那個會覆蓋 `turn_XX.wav`。
- 所有版本留在 `takes/`，選擇紀錄在 `retake.json`。

同一個字在每個版本都念錯（例如「逐人」4 次都變「主人」）時，表示是穩定的讀音，重生沒有用，要改稿：
1. 改 `<scene>.json` 那一句，例如改成「每個人都不一樣」。
2. 把 `takes/turn_XX_k*.wav` 移到 `takes/old_text/`，因為台詞不一樣了，舊版本不能拿來比。
3. 執行 `make_dialogue.py gemini-turns ... --redo XX`，再跑一次 `retake_turns.py --turns XX --takes 2`。

## 7. 重新組裝、試聽、後製

```bash
python3 podcast/make_dialogue.py gemini-turns --script podcast/dialogue/<scene>.json --voices I=D1,C=IV_M --name <name>
python3 podcast/dialogue_qa.py out/dialogue/<name>.wav --script podcast/dialogue/<scene>.json --out out/dialogue/qa_<name>.json --listen
python3 podcast/make_dialogue.py master out/dialogue/<name>.wav podcast/samples/dialogue/<name>.mp3
```

- 組裝時不會打 API，只用已存在的輪次。
- 通過條件：
  - 剩下的錯字都屬於第 5 步列的轉寫問題。
  - 全段最大的取樣跳動小於 0.7。
- 加上 `--listen`，會請 Gemini 3.8 Flash 只聽音檔，給威嚴、不確定感、附和和打斷自然度打分，並列出爆音和換錯人的時間點。
  - 一個檔案約 0.004 美元。
  - 這只能抓到爆音、換錯人這類明顯的問題。
  - **台灣口音不能交給它判斷**，原因見 `PIPELINE.md` 的「不要做的事」。
- `master` 會做 loudnorm -16 LUFS、44.1 kHz、128 kbps 單聲道 mp3。

## 8. 交付

1. mp3 放進 `podcast/samples/dialogue/`。
   - 檔名：`<場景>_<做法>_<聲線>.mp3`，例如 `interview2_which-wire_B_gemini-per-turn_d1-interviewer.mp3`。
2. `qa_*.json`、`retake.json`、`timeline.json` 複製到 `podcast/results/dialogue/<場景>/`。
3. 在 `samples/dialogue/README.md` 加一列，寫上附和和搶話的時間點，方便對照著聽。
4. 在 `RESULTS.md` 補 CER、重生了幾輪、費用。
5. commit、push。

## 不要做的事

- **不要直接交付 Gemini 多人模式（一次請求兩個聲線）的結果。**
  - 每次生成都有 1～3 句短台詞被給錯聲線，重跑或改 style 都沒辦法避免。
  - 真的要用，就跑 `dialogue_qa.py`，再用 `make_dialogue.py patch` 把錯的那句換成逐輪生成的版本。
- **不要用 LUFS 對齊短於 0.4 秒的片段。**
  - 量出來接近靜音，結果被放大幾十 dB 而爆音。
  - 附和一律用 RMS 對齊，`make_dialogue.py` 已經這樣做。
- **不要不加淡入淡出就硬接波形。** 切點本身就是喀一聲。
- **要逐句修正的稿子，不要用 ElevenLabs Text to Dialogue。** 錯一句就要整段重來，字元額度也有限。
- **不要拿「附和」做太多。** 一場 2～4 個，放在對方長句的子句之間；太多會像在打斷。

## 時間與費用（一場約 2.5 分鐘、23 輪）

| 步驟 | 時間 | 費用 |
|---|---|---|
| 4. 逐輪生成（含附和、爆音重生） | 約 3 分鐘 | 約 4,000～5,000 個音訊 token，約 0.04 美元 |
| 5. Breeze 驗收 | 約 3 分鐘 | 0 |
| 6. 重生約 9 輪 × 3 次 | 約 8 分鐘 | 約 5,400 個音訊 token，約 0.05 美元 |
| 7. 組裝、試聽、後製 | 約 3 分鐘 | Gemini 試聽約 0.004 美元 |
| 合計 | 約 20 分鐘 | **約 0.10 美元** |

以 2026 年底前的付費價計算（音訊輸出每百萬 token 9 美元，每秒 25 個 token）。不含 agent 自己寫稿和核對的時間。

## 替代方案

- **A：Gemini 多人模式一次生成**
  - `make_dialogue.py gemini-multi --voices I=IV_F,C=IV_M`
  - 優點：附和、搶話由模型自己演，最自然；設計聲線可以用。
  - 缺點：一定要逐輪檢查有沒有換錯人，並用 `patch` 修補。
- **C：ElevenLabs Text to Dialogue**
  - `make_dialogue.py elevenlabs --voices I=<id>,C=<id>`
  - 聲音庫的台灣聲線最接近台灣口音，沒有換錯人，打斷可以用 `[interrupting]`。
  - 缺點：念錯一句就要整段重來；附和不能重疊。
