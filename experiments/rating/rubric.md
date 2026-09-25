# 盲測評分指引（人類評審）

評審條件：母語為台灣華語、在台灣長大、聽力正常；至少 12 人（建議 16 人，預留淘汰未通過注意力檢查者）。
每人約 40 個片段，20–25 分鐘。用耳機、安靜環境。不告知片段來自哪個模型/聲線。

## 每個片段五個問題

| 欄位 | 量尺 | 說明 |
|---|---|---|
| naturalness_1to5 | 1 很像機器 … 5 像真人 | 整體自然度（MOS） |
| taiwan_flavor_1to5 | 1 明顯中國大陸腔 / 2 偏大陸 / 3 說不上來 / 4 偏台灣 / 5 就是台灣人 | 只評口音與用語，不評音質 |
| pronunciation_errors | 列出唸錯的字詞 | 對照顯示的原文，含破音字、台語詞、英文、數字 |
| emotion_fit_1to5 | 1 完全不對 … 5 完全符合 | 語氣是否符合情境（故事/廣告/客服） |
| would_ship_yes_no | yes / no | 「這段可以直接上線給客人聽嗎？」 |

## 錨點（attention check）
- 高錨：真人台灣配音員錄的同一句（隨機插入 2 個）。評審給高錨 naturalness < 4 或 taiwan_flavor < 4 兩次以上 → 剔除該評審。
- 低錨：故意用 zh-CN 對照聲線 + 大陸用語版本（視頻/軟件）。taiwan_flavor 給 ≥ 4 兩次以上 → 剔除。

## 分析
1. 主效應：模型（Flash / Lite）× 聲線條件（prebuilt / tw_design / ctrl_design / cn_design）× 是否有 style 標註，以混合效應模型或至少配對 Wilcoxon 比較 MOS 與台灣味分數。
2. 陷阱類別通過率：每個 `cat` 的 pronunciation_errors 為空的比例；重點看 hokkien_hanzi、tw_reading、code_switch 三類。
3. 上線率：would_ship=yes 的比例，依情境分開報（客服要求最嚴）。
4. 與自動評審（judge.py）的相關性：若 Spearman ρ > 0.6，之後可用 judge 做回歸測試；否則只當粗篩。

## 通過門檻（建議，可依產品調整）
- 說故事（批次）：MOS ≥ 4.0、台灣味 ≥ 4.0、hokkien_hanzi 通過率 ≥ 80%、長文無說話者漂移。
- 配音（批次）：emotion_fit ≥ 4.0、標籤 (<laugh> 等) 100% 被演出而非唸出。
- 客服（即時）：would_ship ≥ 90%、數字/電話/身分證字號 100% 正確、串流 TTFB p95 ≤ 1.5 s、RTF p95 ≤ 0.5。
