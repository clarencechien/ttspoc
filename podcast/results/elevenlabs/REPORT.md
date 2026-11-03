# ElevenLabs 對照組結果（2026-11-03）

## 結論
- **ElevenLabs 冠軍：EL1 + `eleven_v4`**（Borda 17），全集已產出：`podcast/samples/elevenlabs/ep01_EL.mp3`（7.2 分鐘）。
- 但整體仍輸給 Gemini：S3 Enceladus（24，三次盲評皆第一）> D1 磁性深夜（18）> EL1_v4（17）。
- 原因：評審一致認為 S3/D1 的胸腔共鳴、慵懶深夜感與自嘲細節較好；EL 的 v4 三個聲音都明顯優於 v3（v3 全部墊底），但 EL 音高偏高（F0 中位數 119–146 Hz，D1 只有 94 Hz），「低沉磁性」這點不如 Gemini。
- QA：10 段全部 text_match=1.00，**零誤讀**、無標籤被唸出、無大陸腔或英文詞問題，不需重生。

## Borda 排名（3 次隨機順序，Gemini 評審）
| 名次 | 音檔 | Borda | 各次名次 |
|---|---|---|---|
| 1 | S3_Enceladus（Gemini） | 24 | 1/1/1 |
| 2 | D1_磁性深夜（Gemini） | 18 | 2/5/2 |
| 3 | **EL1_eleven_v4** | 17 | 3/3/4 |
| 4 | EL0_eleven_v4 | 16 | 4/4/3 |
| 5 | EL2_eleven_v4 | 15 | 5/2/5 |
| 6 | EL1_eleven_v3 | 7 | 8/6/6 |
| 6 | EL2_eleven_v3 | 7 | 6/7/7 |
| 8 | EL0_eleven_v3 | 4 | 7/8/8 |

## 客觀指標（試聽片段）
| 音檔 | F0 中位 (Hz) | F0 p10–p90 | 頻譜重心 (Hz) | 長度 (s) |
|---|---|---|---|---|
| D1_磁性深夜 | 93.8 | 82.5–110.1 | 1754 | 21.2 |
| S3_Enceladus | 114.8 | 92.3–149.1 | 2879 | 21.1 |
| EL1_eleven_v3 | 118.8 | 96.4–184.6 | 1158 | 17.7 |
| EL0_eleven_v3 | 120.6 | 102.6–146.3 | 1325 | 17.0 |
| EL2_eleven_v3 | 125.7 | 91.6–165.5 | 1658 | 18.6 |
| EL2_eleven_v4 | 134.1 | 100.4–208.5 | 2056 | 19.2 |
| EL0_eleven_v4 | 135.6 | 107.6–201.7 | 1814 | 18.4 |
| EL1_eleven_v4 | 146.3 | 101.7–218.2 | 1623 | 17.7 |

EL 語速比 Gemini 快約 15%（同一段試聽 17–19 s vs 21 s）。v4 音高起伏較大（p90 > 200 Hz），表情較多但也較不「低沉」。

## 全集分段（EL1 / eleven_v4，全部一次通過）
| 段落 | 音長 (s) | 預估 (s) | 比例 | F0 中位 |
|---|---|---|---|---|
| s00_open | 31.4 | 30.7 | 1.03 | 131.9 |
| s01_copy | 39.3 | 47.6 | 0.83 | 132.6 |
| s02_speed | 34.3 | 33.3 | 1.03 | 140.4 |
| s03_altitude | 45.2 | 55.1 | 0.82 | 135.6 |
| s04_depth | 43.1 | 45.3 | 0.95 | 134.8 |
| s05_judge | 56.6 | 65.3 | 0.87 | 130.4 |
| s06_range | 45.7 | 45.8 | 1.00 | 133.3 |
| s07_resolution | 47.6 | 50.4 | 0.94 | 133.3 |
| s08_efficacy | 41.8 | 45.6 | 0.92 | 129.7 |
| s09_outro | 35.9 | 36.2 | 0.99 | 138.7 |

跨段 F0 差距 10.7 Hz（聲音一致性良好）。每段 TTS 牆鐘時間 6–10 秒。

## QA 誤讀
無。10 段 misreadings 皆為空，tags_read_aloud 皆為 false。

## 計費字元（約略）
- 全集 TTS：約 2,438 字元（log.json 中 chars 加總）
- 試聽：6 次 × 試聽稿；Voice Design 1 次（3 個 preview）
- 確切用量請以 ElevenLabs 後台為準。

## 腳本修正
無。`eleven_v3`、`eleven_v4`、`eleven_ttv_v3` 在此方案下皆可用，`podcast/elevenlabs_tts.py` 未修改。

## 檔案
- `voice_comparison.json`、`qa_EL.json`、`log.json`、`voices.json`（三個已存 voice_id）
- 音檔：`podcast/samples/elevenlabs/`（preview_EL0–2、8 個 audition_*.mp3、ep01_EL.mp3）
