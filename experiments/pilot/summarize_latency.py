"""Render out/latency.jsonl as a markdown table (used for the README pilot section)."""
import json, sys

rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "out/latency.jsonl", encoding="utf-8")]
fmt = lambda v, f: (f % v) if v is not None else "–"
print("| 字數 | 模型 | 模式 | n | TTFB 中位 | 生成時間中位 | 音長中位 | 預期音長 | RTF 中位 | 錯誤 |")
print("|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    exp = r["chars"] / 4.5
    flag = " ⚠️截斷" if r["audio_med"] and r["audio_med"] < 0.6 * exp else ""
    print(f"| {r['chars']} | {r['model_key']} | {r['mode']} | {r['n']} | {fmt(r['ttfb_med'], '%.2f s')} | {fmt(r['wall_med'], '%.1f s')} | "
          f"{fmt(r['audio_med'], '%.0f s')}{flag} | ~{exp:.0f} s | {fmt(r['rtf_med'], '%.2f')} | {len(r['errors'])} |")
