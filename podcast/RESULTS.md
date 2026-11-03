# Podcast POC 結果（2026-11-03）

來源文章：〈記住了第一招，漏掉了第五招〉 https://imitator.ai-apps.work/r/fifth-move
成品：「深夜 Debug」EP01，兩個聲線各一集，約 8 分鐘，Gemini 3.8 Flash TTS 生成。
音檔整理在 `podcast/samples/`（索引見該資料夾的 README），重跑指令見最下方；重跑時的中間檔仍輸出到 `out/podcast/`（不進 git）。

## 結論
- **整條流程一次跑通**：10 段、每段 166–341 字，兩個聲線共 20 段，第一次生成就全部通過音長檢查，沒有出現 pilot 裡的長文截斷。
  每段控制在 350 字以內是有效的做法。
- **聲線**：比較式排名的第一名是 studio 聲線 **Enceladus**（氣聲、低沉、親密），第二名 Charon。
  設計聲線 **D1 磁性深夜** 量測上最低沉（基頻中位數 86–103 Hz），整集聲線最穩，但評審排第四。哪個比較像你要的「磁性」，要靠人耳決定。
- **台灣味**：兩集逐字稿與原稿吻合度都在 95% 以上，自動校對沒有抓到系統性的大陸腔，語助詞自然。
- **英文人名是最大風險**：D1 兩次把「Rieseberg」唸錯，第三次才對；Enceladus 一次就對。專有名詞要逐段校對。
- **成本**：一集約 12,000 audio tokens，Flash 定價下約 US$0.11；生成時間合計約 140 秒，可平行化。

## 選聲
同一句試聽稿（含中英夾雜、自嘲、`<laugh>`），六個候選聲線：

| 聲線 | 類型 | 基頻中位數 | 頻譜重心 | 三次洗牌排名 Borda 分數 |
|---|---|---|---|---|
| S3 Enceladus | studio | 101.7 Hz | 2,370 Hz | **17** |
| S2 Charon | studio | 112.9 Hz | 2,547 Hz | 16 |
| S4 Umbriel | studio | 111.1 Hz | 2,238 Hz | 10 |
| D1 磁性深夜 | 設計 zh-TW | **96.4 Hz** | 2,344 Hz | 8 |
| D2 工程師學長 | 設計 zh-TW | 118.8 Hz | 2,433 Hz | 6 |
| S1 Algieba | studio | 109.1 Hz | 3,192 Hz | 6 |

- 逐段單獨評分時，評審給六個聲線 24 或 25 分（滿分 25），**完全沒有鑑別力**。
  改成六段一起丟、不可並列、洗牌三次後排名，才分得出高下（`compare_voices.py`）。
- Borda 分數：每次排名第一得 6 分、最後一名得 1 分，三次加總，最高 18 分。

## 整集品質
| 項目 | Enceladus | D1 磁性深夜 |
|---|---|---|
| 總長（含片頭片尾） | 8.2 分鐘 | 8.5 分鐘 |
| 段落第一次就通過音長檢查 | 10/10 | 10/10 |
| 各段基頻中位數範圍 | 96–117 Hz | 86–103 Hz |
| 逐字稿吻合度 | 0.98–1.00 | 0.95–1.00 |
| 嚴重錯讀（重生成前） | 1：「角色扮演」 | 1：「Rieseberg」 |
| 重生成後 | 重試 1 次通過 | 重試 3 次通過 |
| 評審標記的大陸讀音 | 「角色」唸 jiǎo sè | 「說服」唸 shuì fú |
| 整集響度 | -16.6 LUFS | -16.9 LUFS |

- 兩個「大陸讀音」標記在台灣口語都很常見，我沒有修。如果要對齊教育部讀音，可在稿子裡換詞避開。
- 模型會自己加「啊」「喔」「呃」等語助詞，評審把它算成多唸。對 podcast 來說這讓口語更自然，保留。
- 片頭片尾是程式合成的短音效，不用任何素材。

## 對「像台灣財經閒聊型 podcast」的定位
- 聲線用一般特徵描述設計，沒有寫任何真人的名字，也沒有複製或模仿真實主持人的聲音；節目名稱與台詞都是自創。
- 「像那種節目」的感覺主要來自稿子：單人、口語、自嘲、離題再拉回、語助詞。聲音本身只負責低沉與放鬆。

## ElevenLabs 對照組（已執行）
由新的子 session 執行，因為原本的容器讀不到 `elevenlabs_key`。完整報告在 `results/elevenlabs/REPORT.md`。
做法：用與 D1 相同的聲線描述做 Voice Design，存下三個候選 EL0 到 EL2，每個用 `eleven_v3` 和 `eleven_v4` 各唸一次試聽稿，
再跟 Gemini 的 Enceladus、D1 一起做三次洗牌排名。

| 名次 | 聲線 | Borda | 基頻中位數 |
|---|---|---|---|
| 1 | Gemini Enceladus | 24（三次都第一） | 114.8 Hz |
| 2 | Gemini D1 磁性深夜 | 18 | 93.8 Hz |
| 3 | ElevenLabs EL1 + v4 | 17 | 146.3 Hz |
| 4 | ElevenLabs EL0 + v4 | 16 | 135.6 Hz |
| 5 | ElevenLabs EL2 + v4 | 15 | 134.1 Hz |
| 6–8 | ElevenLabs 三個聲線 + v3 | 4–7 | 119–126 Hz |

- **v4 明顯勝過 v3**：三個聲線換成 v4 都上升了好幾名。
- **ElevenLabs 輸在「低沉」**：基頻比 Gemini 高 20 到 50 Hz。評審對 EL1 v4 的評語是「音色偏清亮，缺乏深夜廣播的厚實低沉感」。
- **ElevenLabs 唸得最準**：整集 EL1 v4 共 10 段，逐字稿吻合度全部 1.00，自動校對零錯讀，不需要任何重生成。Gemini 兩集各有一段要重做。
- **語速快約 15%**：同一份稿 7.2 分鐘，Gemini 是 8.2 到 8.5 分鐘。
- 響度後製後 -16.7 LUFS，與 Gemini 版一致。

### 三方總表
| | Gemini Enceladus | Gemini D1 磁性深夜 | ElevenLabs EL1 v4 |
|---|---|---|---|
| 比較式排名 | 第 1 | 第 2 | 第 3 |
| 低沉程度 | 中 | 最低沉 | 最高 |
| 唸錯需重生成 | 1 段 | 1 段，重試 3 次 | 0 段 |
| 整集長度 | 8.2 分 | 8.5 分 | 7.2 分 |
| 每集成本 | 約 US$0.11 | 約 US$0.11 | 約 2,400 字元，依方案計 |

## 下一步
1. 人耳挑聲線：聽兩集完整版和六段試聽，決定 Enceladus、D1，或改寫設計描述再生一輪。
2. 人耳盲聽三集：自動評審只是粗篩，「磁性」最終要人判斷。
3. 專有名詞前處理：人名第一次出現時唸全名，之後只唸 Felix；或建立一份讀音對照表，逐段校對時自動比對。
4. 加背景音樂床與段落轉場音效，再做一次盲聽。

## 重跑
```bash
python3 -m pip install -r requirements.txt
python3 podcast/make_podcast.py design                     # 建立 D1/D2 設計聲線（閒置一年後過期）
python3 podcast/make_podcast.py audition                   # 六個聲線同句試聽
python3 podcast/compare_voices.py out/podcast/audition/*.wav
python3 podcast/make_podcast.py episode --voice S3         # 逐段生成 + 音長檢查 + 自動重試
python3 podcast/qa_episode.py S3                           # 逐段校對
python3 podcast/make_podcast.py episode --voice S3 --only s06_range   # 只重生某段
python3 podcast/make_podcast.py master --voice S3          # 片頭片尾、靜音、-16 LUFS、mp3
```
資料：`podcast/results/`（排名、逐段校對、逐段音長紀錄、設計聲線 ID）。
