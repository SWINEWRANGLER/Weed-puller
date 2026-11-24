"""Synthesise a 60 s music bed for the WP-1 sales video (no samples, numpy only).

Structure (seconds): 0-3.5 tense pad + riser, 3.5 impact, 3.5-50 driving
arpeggio groove in A minor (Am F C G), 50-57 breakdown, 57 final hit, ring out.
"""
import sys
import wave
import numpy as np

SR = 44100
DUR = 60.0
BPM = 96
BEAT = 60 / BPM
BAR = BEAT * 4
N = int(SR * DUR)
rng = np.random.default_rng(7)


def t_axis(sec):
    return np.arange(int(sec * SR)) / SR


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env_adsr(n, a=0.01, d=0.2, s=0.6, r=0.3, length=None):
    length = length or n / SR
    t = np.arange(n) / SR
    e = np.where(t < a, t / a, np.where(t < a + d, 1 - (1 - s) * (t - a) / d, s))
    rel_start = max(length - r, a + d)
    e = np.where(t > rel_start, e * np.clip(1 - (t - rel_start) / r, 0, 1), e)
    return e


def lowpass(x, cutoff):
    # one-pole low-pass, cutoff in Hz (scalar)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(0, len(x), 4096):
        seg = x[i:i + 4096]
        out = np.empty_like(seg)
        for k in range(len(seg)):
            acc = (1 - a) * seg[k] + a * acc
            out[k] = acc
        y[i:i + 4096] = out
    return y


def lp_fast(x, cutoff):
    # FFT brick-ish low-pass with soft roll-off (fast for long buffers)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def hp_fast(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (f / cutoff) ** 4 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def saw(freq, t, detune=0.0):
    out = np.zeros_like(t)
    for d in (-detune, 0, detune):
        ph = (t * freq * (1 + d)) % 1.0
        out += 2 * ph - 1
    return out / 3


def reverb(x, seconds=2.4, mix=0.3):
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.2)
    ir = lp_fast(ir, 6000)
    ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + n
    nfft = 1 << (L - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return x * (1 - mix) + y * mix * 1.6


CHORDS = [  # A minor: Am, F, C, G (midi roots + voicing)
    [57, 60, 64, 67, 71],
    [53, 57, 60, 64, 67],
    [48, 52, 55, 60, 64],
    [55, 59, 62, 67, 69],
]


def build():
    pad = np.zeros(N)
    arp = np.zeros(N)
    drums = np.zeros(N)
    bass = np.zeros(N)
    fx = np.zeros(N)

    # --- pads: whole piece, one chord per bar after the intro
    t_intro = t_axis(3.6)
    for n in (45, 52, 57, 59, 64):
        pad[: len(t_intro)] += saw(midi(n), t_intro, 0.004) * np.linspace(0.0, 1.0, len(t_intro)) ** 1.5 * 0.18
    start = 3.5
    bar = 0
    while start < 57:
        ch = CHORDS[bar % 4]
        length = BAR + 0.4
        tt = t_axis(length)
        e = env_adsr(len(tt), a=0.25, d=0.5, s=0.8, r=0.5)
        sig = sum(saw(midi(n), tt, 0.005) for n in ch[1:]) * e * 0.11
        place(pad, sig, start)
        # bass: root on beats, octave down
        for b in range(4):
            bt = t_axis(BEAT * 0.9)
            f = midi(ch[0] - 12)
            s = (np.sin(2 * np.pi * f * bt) + 0.3 * np.sin(4 * np.pi * f * bt)) * env_adsr(len(bt), 0.005, 0.15, 0.5, 0.1)
            if 8.5 <= start + b * BEAT < 50:
                place(bass, s, start + b * BEAT, 0.5)
        # arpeggio: 16ths
        if 8.5 <= start < 50:
            pattern = [0, 2, 3, 4, 3, 2, 1, 2] * 2
            for k, idx in enumerate(pattern):
                at = start + k * BEAT / 4
                nt = ch[idx] + 12
                at_t = t_axis(0.22)
                s = np.sin(2 * np.pi * midi(nt) * at_t) * np.exp(-at_t * 16) + 0.25 * np.sin(4 * np.pi * midi(nt) * at_t) * np.exp(-at_t * 24)
                place(arp, s, at, 0.16 if k % 4 else 0.22)
        # drums
        if 8.5 <= start < 50:
            for b in range(4):
                at = start + b * BEAT
                kt = t_axis(0.35)
                f = 50 + 90 * np.exp(-kt * 30)
                kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-kt * 9)
                if b in (0, 2) or start > 20:
                    place(drums, kick, at, 0.9)
                ht = t_axis(0.06)
                hat = rng.standard_normal(len(ht)) * np.exp(-ht * 70)
                place(drums, hat, at + BEAT / 2, 0.06)
                place(drums, hat, at, 0.035)
                if b in (1, 3) and start > 15:
                    st = t_axis(0.25)
                    snare = rng.standard_normal(len(st)) * np.exp(-st * 18) * 0.6 + np.sin(2 * np.pi * 190 * st) * np.exp(-st * 25)
                    place(drums, snare, at, 0.22)
        start += BAR
        bar += 1

    # final chord + hit at 57
    tt = t_axis(3.0)
    e = env_adsr(len(tt), a=0.02, d=1.0, s=0.5, r=1.8)
    place(pad, sum(saw(midi(n), tt, 0.006) for n in (45, 57, 60, 64, 71)) * e * 0.14, 57.0)

    # --- fx: risers + impacts
    for hit, rise in ((3.5, 2.5), (8.5, 1.5), (57.0, 2.0)):
        rt = t_axis(rise)
        noise = hp_fast(rng.standard_normal(len(rt)), 1500) * (rt / rise) ** 2.5 * 0.25
        place(fx, noise, hit - rise)
        it = t_axis(2.5)
        boom = np.sin(2 * np.pi * np.cumsum(35 + 60 * np.exp(-it * 6)) / SR) * np.exp(-it * 2.2)
        place(fx, boom, hit, 0.9)
        place(fx, lp_fast(rng.standard_normal(len(it)), 3000) * np.exp(-it * 5) * 0.25, hit)

    pad = lp_fast(pad, 2200)
    mix = pad * 0.9 + arp * 0.8 + bass * 0.9 + drums * 0.8 + fx * 0.8
    # sidechain-ish duck under kicks during groove
    mix = reverb(mix, 2.6, 0.28)
    # fades
    fade_in = np.clip(np.arange(N) / (0.8 * SR), 0, 1)
    fade_out = np.clip((N - np.arange(N)) / (1.5 * SR), 0, 1)
    mix *= fade_in * fade_out
    mix /= np.max(np.abs(mix)) + 1e-9
    mix = np.tanh(mix * 1.2) * 0.85
    # stereo width: slightly delayed copy
    d = int(0.012 * SR)
    left = mix
    right = np.concatenate([np.zeros(d), mix[:-d]]) * 0.92 + mix * 0.08
    return np.stack([left, right], axis=1)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "music.wav"
    st = build()
    pcm = (st * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", out)
