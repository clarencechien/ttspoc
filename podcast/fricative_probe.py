"""Objective proxy for retroflex strength: spectral centroid of fricative (sibilant) frames.

Retroflex sibilants (ㄓㄔㄕ, zh/ch/sh) have a lower spectral peak (~2.5-4 kHz) than alveolar ones
(ㄗㄘㄙ, z/c/s, ~5-8 kHz). Taiwan Mandarin tends to deretroflex, so for the SAME text a more Taiwanese
take should show a HIGHER median sibilant centroid. Only compare takes of identical text.

  python podcast/fricative_probe.py clip1.wav clip2.wav ...
"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from compare_voices import load

def sibilant_centroids(x, sr, win=0.02, hop=0.01):
    n, h = int(sr * win), int(sr * hop); w = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / sr); hi = (f >= 2000) & (f <= 11000); lo = (f >= 80) & (f < 1500)
    rms_all = np.sqrt(np.mean(x ** 2)); out = []
    for i in range(0, len(x) - n, h):
        fr = x[i:i + n]
        if np.sqrt(np.mean(fr ** 2)) < 0.15 * rms_all:      # skip silence
            continue
        spec = np.abs(np.fft.rfft(fr * w)) ** 2
        zcr = np.mean(np.abs(np.diff(np.sign(fr)))) / 2
        if spec[hi].sum() > 2.0 * spec[lo].sum() and zcr > 0.25:   # noisy, high-frequency dominated = sibilant
            out.append(float((spec[hi] * f[hi]).sum() / spec[hi].sum()))
    return np.array(out)

if __name__ == "__main__":
    print(f"{'clip':44s} {'sibilant frames':>15s} {'median centroid':>16s} {'p25':>6s} {'p75':>6s}")
    for p in sys.argv[1:]:
        x, sr = load(p); c = sibilant_centroids(x, sr)
        print(f"{Path(p).name:44s} {len(c):15d} {np.median(c):16.0f} {np.percentile(c,25):6.0f} {np.percentile(c,75):6.0f}")
