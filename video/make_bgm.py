"""Synthesize a royalty-free lo-fi electronic music bed → build/bgm.wav (stereo 48 kHz, exactly timeline total).

98 BPM, Am–F–C–G (one chord per bar): filtered detuned-saw pad, plucky triangle arpeggio,
sub bass, soft kick on 1 & 3, swung closed hats. Energy lifts at 199 s and 223 s, fades in/out.
"""
import json
import os
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
HERE = Path(__file__).parent
TOTAL = float(os.environ.get("BGM_TOTAL") or json.load(open(HERE / "timeline.json"))["total"])
N = int(round(TOTAL * SR))
BEAT = 60 / 98
BAR = 4 * BEAT
rng = np.random.default_rng(7)
t = np.arange(N) / SR

# chord tones as MIDI notes: root (bass), voicing (pad), arp pattern notes
CHORDS = [  # Am, F, C, G
    (45, [57, 60, 64, 67], [69, 72, 76, 79]),
    (41, [57, 60, 65, 69], [69, 72, 77, 81]),
    (48, [55, 60, 64, 67], [67, 72, 76, 79]),
    (43, [55, 59, 62, 67], [67, 71, 74, 79]),
]
hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def energy(tt):
    """0..1 arrangement intensity: soft start, build after the intro, lifts at 199 s and 223 s."""
    e = 0.75 + 0.1 * np.clip((tt - 8) / 20, 0, 1)
    e += 0.08 * np.clip((tt - 197) / 4, 0, 1) + 0.07 * np.clip((tt - 221) / 4, 0, 1)
    return e


def add(buf, start, sig):
    i = int(start * SR)
    if i < 0:
        sig, i = sig[-i:], 0
    if i >= N:
        return
    j = min(N, i + len(sig))
    buf[i:j] += sig[: j - i]


L = np.zeros(N)
R = np.zeros(N)

# --- pad: detuned saws per bar, crossfaded, low-passed ---
padL = np.zeros(N)
padR = np.zeros(N)
nbar = int(np.ceil(TOTAL / BAR)) + 1
seg = int(BAR * SR) + int(0.3 * SR)
ts = np.arange(seg) / SR
env = np.minimum(1, ts / 0.25) * np.minimum(1, (seg / SR - ts) / 0.3)
for b in range(nbar):
    _, pad, _ = CHORDS[b % 4]
    sl = np.zeros(seg)
    sr_ = np.zeros(seg)
    for m in pad:
        f = hz(m)
        for d, side in ((-0.12, sl), (0.12, sr_)):
            ph = (f * 2 ** (d / 12 / 4) * ts + rng.random()) % 1.0
            side += (2 * ph - 1) * 0.6 + np.sin(2 * np.pi * f * ts) * 0.4
    add(padL, b * BAR - 0.15, sl * env)
    add(padR, b * BAR - 0.15, sr_ * env)
wob = 1 + 0.15 * np.sin(2 * np.pi * t / (BAR * 2))  # slow breathing
padL = lp(padL, 1100, 4) * wob * 0.05
padR = lp(padR, 1100, 4) * wob * 0.05
L += padL
R += padR

# --- arpeggio: plucky triangle 8ths, ping-pong pan ---
pl = int(0.45 * SR)
tp = np.arange(pl) / SR
step = BEAT / 2
order = [0, 1, 2, 3, 2, 1, 2, 3]
k = 0
while k * step < TOTAL:
    st = k * step
    _, _, arp = CHORDS[int(st // BAR) % 4]
    f = hz(arp[order[k % 8]])
    tri = 2 * np.abs(2 * ((f * tp) % 1.0) - 1) - 1
    note = tri * np.exp(-tp * 9) * np.minimum(1, tp / 0.004)
    g = 0.055 * float(energy(np.array([st]))[0]) * (1.0 if k % 2 == 0 else 0.8)
    pan = 0.3 + 0.4 * (k % 2)
    add(L, st, note * g * (1 - pan) * 2)
    add(R, st, note * g * pan * 2)
    k += 1
# soften arp transients with a gentle low-pass
L = lp(L - padL, 3500) + padL
R = lp(R - padR, 3500) + padR

# --- sub bass: sine on the root, pulses on each beat ---
bl = int(BEAT * SR)
tb = np.arange(bl) / SR
benv = np.minimum(1, tb / 0.01) * np.exp(-tb * 2.2)
for b in range(int(TOTAL / BEAT) + 1):
    root = CHORDS[int(b * BEAT // BAR) % 4][0]
    f = hz(root)
    s = (np.sin(2 * np.pi * f * tb) + 0.2 * np.sin(4 * np.pi * f * tb)) * benv * 0.13
    add(L, b * BEAT, s)
    add(R, b * BEAT, s)

# --- drums (enter after the 2 s intro) ---
kl = int(0.35 * SR)
tk = np.arange(kl) / SR
kick = np.sin(2 * np.pi * (45 * tk + (110 - 45) / 30 * (1 - np.exp(-30 * tk)))) * np.exp(-tk * 9) * 0.32
hl = int(0.06 * SR)
th = np.arange(hl) / SR
hat = hp(rng.standard_normal(hl), 7000) * np.exp(-th * 70)
hat = lp(hat, 11000) * 0.035
swing = BEAT * 0.08
first = int(np.ceil(2.0 / BEAT))
for b in range(first, int(TOTAL / BEAT) + 1):
    st = b * BEAT
    e = float(energy(np.array([st]))[0])
    if b % 2 == 0:  # beats 1 and 3
        add(L, st, kick * e)
        add(R, st, kick * e)
    for off, g in ((0, 0.8), (BEAT / 2 + swing, 1.0)):
        add(L, st + off, hat * g * e * 0.8)
        add(R, st + off, hat * g * e * 1.1)
    if st > 199:  # lift: ghost 16th hats
        add(L, st + BEAT * 0.75 + swing / 2, hat * 0.45 * e)
        add(R, st + BEAT * 0.75 + swing / 2, hat * 0.55 * e)

# --- master: arrangement fades, gentle glue, normalise ---
fade = np.minimum(1, t / 2.0) * np.clip((TOTAL - t) / 5.0, 0, 1)
L *= fade
R *= fade
mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 1.2) / 1.2  # soft saturation, no hard clipping
mix *= 0.7 / np.max(np.abs(mix))  # peak -3 dBFS
out = HERE / "build" / "bgm.wav"
out.parent.mkdir(exist_ok=True)
wavfile.write(out, SR, (mix * 32767).astype(np.int16))
assert len(mix) == N
print(f"wrote {out} {N / SR:.3f}s")
