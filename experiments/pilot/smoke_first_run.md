# 第一次冒煙測試（2026-09-25）
句子：「欸，歹勢齁，我們這邊查一下喔。您的訂單在西門町門市，明天下午三點前可以取貨，記得帶身分證件，有問題再 call 我們 0800 客服專線喔。」（60 字 → 55 text tokens）

| 模型 | 模式 | wall | TTFB | 音長 | audio tokens |
|---|---|---|---|---|---|
| flash-lite | unary | 5.81 s | – | 13.4 s | 429 |
| flash-lite | stream | 3.56 s | 0.48 s | 13.5 s | – |
| flash | unary | 6.01 s | – | 13.3 s | 425 |
| flash | stream | 12.18 s | 1.66 s | 13.9 s | – |

短句「好的，幫您查詢一下，請稍等喔。」× 3：lite TTFB 中位 0.96 s（0.91–1.50），flash 1.46 s（1.36–1.94）。

自動評審（gemini-3.8-flash 聽音檔）：兩個模型都判定台灣國語 0.98；但「歹勢」lite 被聽成「等一下」、flash 被聽成「戴先」→ 台語漢字是弱點。
雙人故事（阿嬤 Sulafat + 阿明 Puck，lite）：7.44 s 生成 20.6 s 音檔，<laugh>/<sigh> 有演出，「呷飽未」正確。
語音設計 zh-TW（store=true）：成功，回傳 voice_30etwdi80a4n，一年效期，sample 被評審判定台灣國語 0.95。
