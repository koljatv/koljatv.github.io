#!/usr/bin/env python3
"""The PREVISÃO DO TEMPO music bed: 72 s of light bossa (nylon guitar, vibraphone, shaker, rim), composed for
KÖLJA TV and synthesised here with numpy: no samples, no third-party music. Writes tools/meteo/trilha.m4a.

  python3 tools/meteo/trilha.py   (needs numpy and ffmpeg; run once, the result is in git)
"""
import os, subprocess
import numpy as np

SR, BPM, DUR = 44100, 120, 72.0
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(1102)
N = int(SR * DUR) + SR
L, R = np.zeros(N), np.zeros(N)

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}


def hz(name, octave):
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave + 1) - 69) / 12)


def midi_hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def pluck(f, dur=1.6, bright=0.5):
    """Karplus-Strong nylon string."""
    n = int(SR * dur)
    p = max(2, int(SR / f))
    buf = rng.uniform(-1, 1, p)
    buf = np.convolve(buf, np.ones(3) / 3, mode="same") * (0.6 + 0.4 * bright)  # a soft thumb, not a pick
    out = np.empty(n)
    damp = 0.4985 + 0.0012 * bright
    k = 0
    for i in range(n):  # the plucked string loop
        out[i] = buf[k]
        nxt = (k + 1) % p
        buf[k] = damp * (buf[k] + buf[nxt])
        k = nxt
    out *= np.minimum(1, np.linspace(0, dur, n)[::-1] / 0.08)  # no click at the end
    r = f * (p + 0.5) / SR  # the loop's period is p + 1/2 samples: retune to the exact pitch
    return np.interp(np.arange(0, n - 1, r), np.arange(n), out)


def vib(f, dur=2.2):
    """Vibraphone: a sine with its 4th partial, soft mallet, motor tremolo."""
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t * 1.7) * np.minimum(1, t / 0.004)
    trem = 1 + 0.18 * np.sin(2 * np.pi * 5.2 * t)
    s = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 7) + 0.05 * np.sin(2 * np.pi * f * 10 * t) * np.exp(-t * 20)
    return s * env * trem


def shaker(dur=0.09, amp=1.0):
    n = int(SR * dur)
    s = rng.normal(0, 1, n)
    s = np.diff(s, prepend=0)  # brighter than plain noise, softer than a hi-hat
    s = np.convolve(s, np.ones(4) / 4, mode="same")
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return s * env * amp * 0.03


def rim():
    t = np.arange(int(SR * 0.06)) / SR
    return (np.sin(2 * np.pi * 1750 * t) * 0.6 + rng.normal(0, 0.4, len(t))) * np.exp(-t * 90)


def sub(f, dur):
    t = np.arange(int(SR * dur)) / SR
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 2.2) * np.minimum(1, t / 0.01)


# chords: name, bass (midi), voicing (midi): the 8-bar loop, played four times between an intro and an ending
CH = {
    "Fmaj7": (41, [57, 60, 64, 65]), "Em7": (40, [55, 59, 62, 64]), "A7": (45, [55, 61, 64, 67]),
    "Dm7": (38, [57, 60, 62, 65]), "G7": (43, [53, 59, 62, 65]), "Cmaj7": (36, [55, 59, 60, 64]),
    "C6": (36, [55, 57, 60, 64]), "Cmaj9": (36, [55, 59, 62, 64]),
}
LOOP = ["Fmaj7", "Fmaj7", "Em7", "A7", "Dm7", "G7", "Cmaj7", "C6"]
bars = ["Cmaj9", "G7"] + LOOP * 4 + ["Dm7", "Cmaj9"]  # 36 bars = 72 s

# the melody (vibraphone): (bar of the loop, beat, midi, beats long), over the loop's second and fourth times
MEL = [(0, 0, 72, 1.5), (0, 1.5, 69, 0.5), (0, 2, 67, 2), (1, 0, 69, 1), (1, 1, 72, 1), (1, 2.5, 76, 1.5),
       (2, 0, 74, 1.5), (2, 1.5, 71, 0.5), (2, 2, 67, 2), (3, 0, 73, 1), (3, 1, 76, 1), (3, 2, 79, 2),
       (4, 0, 77, 1.5), (4, 1.5, 74, 0.5), (4, 2, 72, 2), (5, 0, 71, 1), (5, 1, 74, 1), (5, 2, 77, 1.5),
       (6, 0, 76, 3), (7, 0, 79, 1), (7, 1.5, 76, 0.5), (7, 2, 72, 2)]

for b, name in enumerate(bars):
    t0 = b * BAR
    bass, voicing = CH[name]
    last = b == len(bars) - 1
    if last:  # the ending: one strum, let it ring
        for k, m in enumerate([bass] + voicing):
            add(pluck(midi_hz(m), 3.5, 0.4), t0 + k * 0.03, pan=-0.25, gain=0.5)
        add(sub(midi_hz(bass), 3.0), t0, gain=0.35)
        for k, m in enumerate([76, 79, 83]):
            add(vib(midi_hz(m), 3.5), t0 + 0.05 + k * 0.12, pan=0.3, gain=0.22)
        continue
    # the thumb: root on 1, fifth on 3 (bossa bass)
    for beat, m in ((0, bass), (2, bass + 7 if bass + 7 < 50 else bass - 5)):
        add(pluck(midi_hz(m), 1.4, 0.3), t0 + beat * BEAT, pan=-0.2, gain=0.55)
        add(sub(midi_hz(m), 0.9), t0 + beat * BEAT, gain=0.18)
    # the fingers: the chord on the bossa's off-beats
    for e, acc in ((0, 0.9), (3, 0.75), (6, 0.8)) if b % 2 == 0 else ((2, 0.75), (5, 0.8)):
        for k, m in enumerate(voicing):
            add(pluck(midi_hz(m), 0.9, 0.45), t0 + e * BEAT / 2 + k * 0.008, pan=-0.35, gain=0.17 * acc)
    # shaker in sixteenths, rim on the clave
    if b >= 2:
        for s16 in range(16):
            amp = 1.0 if s16 % 4 == 0 else (0.7 if s16 % 2 == 0 else 0.45)
            add(shaker(amp=amp), t0 + s16 * BEAT / 4 + rng.normal(0, 0.003), pan=0.45, gain=0.9 if b < len(bars) - 2 else 0.5)
        for e in ((0, 3, 6) if b % 2 == 0 else (2, 4)):
            add(rim(), t0 + e * BEAT / 2, pan=0.15, gain=0.10)
    # the melody on the loop's 2nd and 4th time
    lb = b - 2
    if 0 <= lb < 32 and (lb // 8) in (1, 3):
        for bar, beat, m, ln in MEL:
            if bar == lb % 8:
                add(vib(midi_hz(m), max(1.2, ln * BEAT + 0.8)), t0 + beat * BEAT, pan=0.3, gain=0.2)
    elif 0 <= lb < 32 and (lb // 8) == 2 and lb % 2 == 0:  # the third time: a soft vibes pad
        for k, m in enumerate(voicing[1:]):
            add(vib(midi_hz(m + 12), 3.0), t0 + k * 0.05, pan=0.3, gain=0.07)


def reverb(x, mix=0.16):
    ir_n = int(SR * 1.6)
    t = np.arange(ir_n) / SR
    ir = rng.normal(0, 1, ir_n) * np.exp(-t * 4.0)
    ir[:int(SR * 0.012)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    wet = np.fft.irfft(np.fft.rfft(x, len(x) + ir_n) * np.fft.rfft(ir, len(x) + ir_n))[:len(x)]
    return x + mix * wet


L, R = reverb(L), reverb(R)
n = int(SR * DUR)
mix = np.stack([L[:n], R[:n]], 1)
fade = np.ones(n)
fade[-int(SR * 1.2):] = np.linspace(1, 0, int(SR * 1.2)) ** 1.5
mix *= fade[:, None]
mix /= np.abs(mix).max() / 0.89
here = os.path.dirname(os.path.abspath(__file__))
wav = os.path.join(here, "trilha.wav")
pcm = (mix * 32767).astype("<i2")
import wave
with wave.open(wav, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR),
                "-c:a", "aac", "-b:a", "160k", os.path.join(here, "trilha.m4a")], check=True)
os.remove(wav)
print("wrote", os.path.join(here, "trilha.m4a"))
