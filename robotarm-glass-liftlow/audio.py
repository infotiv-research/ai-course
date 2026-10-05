"""Sound track for scene.py: an 8 s seamless loop (48 kHz stereo WAV).

Synthesised from scratch with numpy, timed to the animation's loop phase u in [0, 1):
a soft pad bed, servo whine while the arm moves, a higher roll-motor note while the O
spins, gripper clicks, a glass clink when the O is set back, and for the sign a falling
whoosh, a thud and string twang when the strings catch it, small rattles as it bounces,
and a ratcheting winch as it is hoisted out. Every event is mixed modulo the loop
length, so tails wrap round and the end flows into the start.

    blender -b --factory-startup -P audio.py -- out/robotarm_glass_liftlow.wav   (via ./build.sh)
"""
import sys
import wave

import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = "/work/" + (ARGS[0] if ARGS else "out/robotarm_glass_liftlow.wav")
SR, DUR = 48000, 8.0                    # LOOP=240 frames at 30 fps
N = int(SR * DUR)
TAU = 2 * np.pi
rng = np.random.default_rng(7)
t = np.arange(N) / SR
mix = np.zeros((2, N))


def at(u):
    return u * DUR                       # loop phase -> seconds


def add(sig, start_s, pan=0.0, gain=1.0):
    """Mix a mono signal in at start_s, wrapping round the loop; pan -1 (L) .. 1 (R)."""
    idx = (int(start_s * SR) + np.arange(len(sig))) % N
    lg, rg = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    np.add.at(mix[0], idx, sig * gain * lg)
    np.add.at(mix[1], idx, sig * gain * rg)


def loopf(f):
    return round(f * DUR) / DUR           # whole cycles per loop -> seamless


def lowpass(x, cutoff):
    """One-pole low-pass; cutoff may be an array (Hz per sample)."""
    a = np.exp(-TAU * np.broadcast_to(cutoff, x.shape) / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = a[i] * acc + (1 - a[i]) * x[i]
        y[i] = acc
    return y


def env(n, attack, decay):
    k = np.arange(n) / SR
    return np.minimum(k / max(attack, 1e-4), 1.0) * np.exp(-k / decay)


def bell(freqs, dur, decay):
    k = np.arange(int(dur * SR)) / SR
    return sum(np.sin(TAU * f * k) * np.exp(-k / (decay / (1 + i * 0.6)))
               for i, f in enumerate(freqs)) / len(freqs)


def pluck(f, dur, damp=0.996):
    """Karplus-Strong string."""
    p = int(SR / f)
    buf = rng.uniform(-1, 1, p)
    out = np.empty(int(dur * SR))
    for i in range(len(out)):
        out[i] = buf[i % p]
        buf[i % p] = damp * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return out


# ---- pad bed: A major add9, two slow breaths per loop, detuned a hair per channel
for f, g in ((110, 0.5), (164.75, 0.35), (207.75, 0.25), (246.875, 0.22), (277.125, 0.16)):
    breath = 0.75 + 0.25 * np.sin(TAU * 0.25 * t)
    for ch, det in ((0, -0.125), (1, 0.125)):
        ff = loopf(f) + det
        tone = np.sin(TAU * ff * t) + 0.3 * np.sin(TAU * 2 * ff * t) + 0.1 * np.sin(TAU * 3 * ff * t)
        mix[ch] += 0.05 * g * breath * tone

# ---- servos: whine follows the arm's speed on each move of the tool path
MOVES = [(0.10, 0.28), (0.28, 0.36), (0.41, 0.53), (0.70, 0.82), (0.87, 0.93), (0.93, 1.00)]
speed = np.zeros(N)
u = t / DUR
for a, b in MOVES:
    x = (u - a) / (b - a)
    speed = np.maximum(speed, np.where((x > 0) & (x < 1), np.sin(np.pi * np.clip(x, 0, 1)) ** 1.5, 0))
freq = 150 + 240 * speed
ph = np.cumsum(TAU * freq / SR)
servo = (np.sin(ph) + 0.45 * np.sin(2 * ph) + 0.2 * np.sin(3.01 * ph)) * speed
servo += 0.35 * lowpass(rng.normal(0, 1, N), 900) * speed
mix += 0.11 * servo * np.array([[0.75], [1.0]])           # the robot stands right of centre

# roll motor while the O turns 360 degrees (u 0.535 .. 0.695)
x = (u - 0.535) / 0.16
roll = np.where((x > 0) & (x < 1), np.sin(np.pi * np.clip(x, 0, 1)), 0)
ph = np.cumsum(TAU * (380 + 160 * roll) / SR)
mix += 0.07 * (np.sin(ph) + 0.3 * np.sin(2 * ph)) * roll

# ---- gripper clicks (close on the O, open after setting it back) and the glass clink
click = rng.normal(0, 1, int(0.03 * SR)) * env(int(0.03 * SR), 0.0005, 0.004)
click += 0.6 * bell([2400, 3900], 0.03, 0.006)
for uc in (0.385, 0.845):
    add(click, at(uc), pan=0.15, gain=0.5)
    add(click, at(uc) + 0.045, pan=0.15, gain=0.3)
add(bell([2093, 3322, 4710, 6250], 1.2, 0.5), at(0.815), pan=0.05, gain=0.22)
add(bell([1567, 2489], 0.8, 0.35), at(0.37), pan=0.05, gain=0.08)   # glass touch on grasp

# status chime as the robot wakes (ring teal -> orange) and as it rests again
add(bell([659.25, 1318.5], 1.4, 0.6), at(0.04), pan=0.5, gain=0.10)
add(bell([880, 1760], 1.4, 0.6), at(0.04) + 0.16, pan=0.5, gain=0.09)
add(bell([880, 1760], 1.4, 0.6), at(0.96), pan=0.5, gain=0.07)
add(bell([659.25, 1318.5], 1.4, 0.6), at(0.96) + 0.16, pan=0.5, gain=0.07)

# ---- the sign: whoosh as it falls (u 0 .. 0.06), then caught by its strings
FALL = at(0.06)
n = int(FALL * SR)
k = np.arange(n) / n
whoosh = lowpass(rng.normal(0, 1, n), 300 + 4200 * k ** 2) * k ** 2
add(whoosh, 0.0, pan=-0.1, gain=0.55)
thud = np.sin(TAU * 58 * np.arange(int(0.5 * SR)) / SR) * env(int(0.5 * SR), 0.002, 0.09)
add(thud, FALL, gain=0.5)
add(rng.normal(0, 1, int(0.02 * SR)) * env(int(0.02 * SR), 0.0003, 0.004), FALL, gain=0.3)
add(pluck(196.0, 2.2), FALL, pan=-0.35, gain=0.20)       # the two strings snap taut
add(pluck(233.08, 2.2), FALL + 0.012, pan=0.35, gain=0.18)
# glass rattles on the first bounces (bounce: 1.9 Hz, decay 1.6/s)
for j in range(1, 6):
    tb = j / (2 * 1.9)
    add(bell([3100 + 300 * j, 4400], 0.25, 0.06), FALL + tb, pan=-0.05, gain=0.09 * np.exp(-1.6 * tb))

# ---- hoist: winch motor + ratchet clicks, u 0.88 .. 1.0 (wraps into the next drop)
h0, h1 = at(0.88), DUR
n = int((h1 - h0) * SR)
k = np.arange(n) / n
henv = np.sin(np.pi * k) ** 0.7
ph = np.cumsum(TAU * (95 + 70 * henv) / SR)
add((np.sin(ph) + 0.5 * np.sin(2 * ph)) * henv, h0, gain=0.07)
for tc in np.arange(0, h1 - h0, 1 / 16):
    add(click, h0 + tc, pan=-0.1, gain=0.18 * np.sin(np.pi * tc / (h1 - h0)) ** 0.5)

# ---- master: gentle limiter, normalise to -1 dBFS, write 16-bit stereo
mix = np.tanh(1.4 * mix)
mix *= 10 ** (-1 / 20) / np.max(np.abs(mix))
pcm = (mix.T * 32767).astype("<i2")
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", OUT)
