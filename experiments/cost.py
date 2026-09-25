"""Cost / throughput envelope for the batch use cases (story library, dubbing) and the
real-time one (customer service). Numbers from tts_client.PRICE (launch pricing, doubles 2027-01-01)
and the measured 32 audio tokens/sec.

  python experiments/cost.py --hours 100            # 100 h of story audio
  python experiments/cost.py --calls 1000000 --sec 6 # 1M customer-service turns of ~6 s
"""
import argparse
from tts_client import PRICE, AUDIO_TOKENS_PER_SEC

def per_minute(model_key, batch=False, year2027=False):
    p = PRICE[model_key]; rate = p["audio_out_batch"] if batch else p["audio_out"]
    text = 60 * 4 / 1e6 * p["text_in"]          # ~4 chars/sec speech ≈ 4 text tokens/sec
    audio = 60 * AUDIO_TOKENS_PER_SEC / 1e6 * rate
    return (text + audio) * (2 if year2027 else 1)

def main(a):
    print(f"assumptions: {AUDIO_TOKENS_PER_SEC:.0f} audio tok/s, ~4 text tok/s; USD")
    print(f"{'model':6s} {'mode':8s} {'$/min':>8s} {'$/hour':>8s} {'$/hour 2027':>12s}")
    for m in ("lite", "flash"):
        for mode, b in (("online", False), ("batch", True)):
            pm = per_minute(m, b); print(f"{m:6s} {mode:8s} {pm:8.4f} {pm*60:8.2f} {per_minute(m,b,True)*60:12.2f}")
    if a.hours:
        print(f"\n{a.hours} h of long-form audio:")
        for m in ("lite", "flash"):
            print(f"  {m:6s} online ${per_minute(m)*60*a.hours:,.0f}   batch ${per_minute(m,True)*60*a.hours:,.0f}")
        print(f"  requests needed at ≤ ~8 min/request (16,384 out-token cap): ≥ {a.hours*60/8:,.0f}")
    if a.calls:
        print(f"\n{a.calls:,} realtime turns × {a.sec}s:")
        for m in ("lite", "flash"):
            print(f"  {m:6s} ${per_minute(m)/60*a.sec*a.calls:,.0f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--hours", type=float, default=0)
    ap.add_argument("--calls", type=int, default=0); ap.add_argument("--sec", type=float, default=6)
    main(ap.parse_args())
