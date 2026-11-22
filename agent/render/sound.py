#!/usr/bin/env python3
"""Original soundtrack for a reel: a short beat plus sound effects.

Everything is synthesized here (no samples, no music from anyone else),
so the audio is the page's own and safe to publish.

  - music bed: kick, clap, hi-hats, bass, soft chords and a light arpeggio;
    tempo, key, chords and pattern vary with the seed so reels don't all
    sound the same;
  - a "whoosh" at every scene change, a "pop" when each text appears,
    and a "ding" on the final follow card.

Library:  make_soundtrack([2.6, 2.8, 2.4, 3.0], "out.wav", seed=7, cta_index=3)
CLI:      python3 sound.py out.wav 2.6 2.8 2.4 3.0 [--seed 7] [--cta-last]
Needs numpy and scipy (pip install --break-system-packages numpy scipy).
"""
import random
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100

PROGRESSIONS = [
    # chord roots as semitones from the key, with chord quality
    [(9, "m"), (5, ""), (0, ""), (7, "")],      # vi IV I V
    [(0, ""), (7, ""), (9, "m"), (5, "")],      # I V vi IV
    [(9, "m"), (7, ""), (5, ""), (7, "")],      # vi V IV V
    [(0, ""), (9, "m"), (5, ""), (7, "")],      # I vi IV V
]


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _filt(x, kind, cutoff, order=2):
    sos = butter(order, cutoff, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def _midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def _place(buf, sig, start_s, gain=1.0, pan=0.0):
    """Add a mono signal into a stereo buffer at start_s, with equal-power pan (-1..1)."""
    i = int(start_s * SR)
    if i >= buf.shape[0] or i + len(sig) <= 0:
        return
    if i < 0:
        sig, i = sig[-i:], 0
    sig = sig[: buf.shape[0] - i]
    ang = (pan + 1) * np.pi / 4
    buf[i:i + len(sig), 0] += sig * gain * np.cos(ang)
    buf[i:i + len(sig), 1] += sig * gain * np.sin(ang)


# ---------- drums and instruments ----------

def kick():
    t = _t(0.45)
    f = 45 + 85 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16)
    click = _filt(np.random.randn(len(t)), "highpass", 2000) * np.exp(-t / 0.003) * 0.3
    return body + click


def clap():
    t = _t(0.32)
    noise = _filt(np.random.randn(len(t)), "bandpass", [900, 5000])
    env = np.exp(-t / 0.075)
    for d in (0.008, 0.017):
        env += 0.6 * np.exp(-np.clip(t - d, 0, None) / 0.004) * (t >= d)
    return noise * env * 0.5


def hat(open_=False):
    t = _t(0.25 if open_ else 0.07)
    noise = _filt(np.random.randn(len(t)), "highpass", 7500)
    return noise * np.exp(-t / (0.09 if open_ else 0.022)) * 0.6


def bass_note(freq, dur):
    t = _t(dur)
    s = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    env = np.minimum(1, t / 0.005) * np.exp(-t / (dur * 1.6))
    env[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return _filt(s * env, "lowpass", 500)


def pad_chord(freqs, dur):
    t = _t(dur)
    out = np.zeros(len(t))
    for f in freqs:
        for det in (-0.004, 0.004):
            ff = f * (1 + det)
            out += sum(np.sin(2 * np.pi * k * ff * t) / k for k in range(1, 6))
    out = _filt(out / (len(freqs) * 2), "lowpass", 1600)
    att, rel = min(0.25, dur / 3), min(0.35, dur / 3)
    env = np.minimum(1, t / att) * np.minimum(1, (dur - t) / rel)
    return out * env


def pluck(freq, dur=0.35):
    t = _t(dur)
    s = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t)
    return s * np.exp(-t / 0.12) * np.minimum(1, t / 0.003)


# ---------- sound effects ----------

def whoosh(dur=0.5):
    t = _t(dur)
    noise = np.random.randn(len(t))
    lo = _filt(noise, "bandpass", [250, 1200])
    mid = _filt(noise, "bandpass", [1200, 3500])
    hi = _filt(noise, "bandpass", [3500, 9000])
    x = t / dur
    sweep = lo * (1 - x) ** 2 + mid * 2 * x * (1 - x) + hi * x ** 2
    return sweep * np.sin(np.pi * x) ** 2 * 0.9


def pop():
    t = _t(0.1)
    f = 500 + 800 * np.exp(-t / 0.012)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.03)


def ding(f0=1318.5):
    t = _t(1.6)
    s = (np.sin(2 * np.pi * f0 * t) * np.exp(-t / 0.9)
         + 0.5 * np.sin(2 * np.pi * f0 * 2.76 * t) * np.exp(-t / 0.35)
         + 0.25 * np.sin(2 * np.pi * f0 * 5.4 * t) * np.exp(-t / 0.18))
    return s * np.minimum(1, t / 0.002) * 0.6


# ---------- assembly ----------

def music_bed(total, rng):
    bpm = rng.choice([92, 96, 100, 104, 108])
    beat = 60 / bpm
    bar = 4 * beat
    key = 48 + rng.choice([0, 2, 3, 5, 7, 8])         # C3..G#3
    prog = rng.choice(PROGRESSIONS)
    sixteenth_hats = rng.random() < 0.5
    arp_on = rng.random() < 0.7
    kick_extra = rng.random() < 0.5
    buf = np.zeros((int(SR * (total + 1.0)), 2))
    nbars = int(np.ceil(total / bar)) + 1
    for b in range(nbars):
        t0 = b * bar
        root, qual = prog[b % len(prog)]
        third = 3 if qual == "m" else 4
        chord = [key + 12 + root, key + 12 + root + third, key + 12 + root + 7]
        _place(buf, pad_chord([_midi(n) for n in chord], bar + 0.35), t0 - 0.05, 0.4)
        bass_pat = [1, 0, 1, 1, 0, 1, 1, 0]
        for i, on in enumerate(bass_pat):
            if on:
                _place(buf, bass_note(_midi(key - 12 + root), beat / 2), t0 + i * beat / 2, 0.55)
        for k in (0, 2) + ((2.5,) if kick_extra else ()):
            _place(buf, kick(), t0 + k * beat, 0.95)
        for c in (1, 3):
            _place(buf, clap(), t0 + c * beat, 0.3, pan=0.1)
        steps = 16 if sixteenth_hats else 8
        for i in range(steps):
            vel = 0.11 if i % 2 == 0 else 0.06
            _place(buf, hat(open_=(i == steps - 1)), t0 + i * bar / steps, vel, pan=-0.25)
        if arp_on:
            arp = chord + [chord[0] + 12]
            for i in range(8):
                n = arp[rng.choice([0, 1, 2, 3])] + 12
                _place(buf, pluck(_midi(n)), t0 + i * beat / 2, 0.12, pan=0.3 if i % 2 else -0.3)
    peak = np.max(np.abs(buf)) or 1
    return buf / peak * 0.5


def make_soundtrack(durations, out_wav, seed=None, cta_index=None):
    rng = random.Random(seed)
    np.random.seed(rng.randrange(2 ** 31))
    total = float(sum(durations))
    mix = music_bed(total, rng) * 0.6
    starts = np.cumsum([0] + list(durations[:-1]))
    for i, s in enumerate(starts):
        if i > 0:
            _place(mix, whoosh(), s - 0.25, 0.45, pan=rng.uniform(-0.4, 0.4))
        if cta_index is not None and i == cta_index:
            _place(mix, ding(), s + 0.12, 0.42)
        else:
            _place(mix, pop(), s + 0.08, 0.4)
    mix = mix[: int(SR * total)]
    mix = np.tanh(mix * 1.2) / np.tanh(1.2)
    n_in, n_out = int(0.03 * SR), int(0.5 * SR)
    mix[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    mix[-n_out:] *= np.linspace(1, 0, n_out)[:, None]
    mix = mix / (np.max(np.abs(mix)) or 1) * 0.89
    pcm = (mix * 32767).astype("<i2")
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_wav


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    seed = None
    if "--seed" in args:
        i = args.index("--seed")
        seed = int(args[i + 1])
        del args[i:i + 2]
    cta_last = "--cta-last" in args
    args = [a for a in args if a != "--cta-last"]
    durs = [float(x) for x in args[1:]]
    make_soundtrack(durs, args[0], seed, cta_index=len(durs) - 1 if cta_last else None)
    print(args[0])
