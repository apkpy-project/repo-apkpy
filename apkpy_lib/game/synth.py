"""Game sounds and short tunes, synthesised from numbers: the Studio's "Make a sound", and the sounds of the genre
templates, made when a project is created (so the package carries no sound files).

    make_sound("coin", pitch=1.0, length=1.0, seed=0) -> samples      make_music("happy", speed=1.0, seed=0)
    write_wav(path, samples)                                        make_recipe(folder): sounds.json -> WAV files

The same kind and seed always give the same sound.
"""
import json
import math
import os
import random
import struct
import wave
import zlib

RATE = 22050
KINDS = ("jump", "coin", "laser", "explosion", "hit", "power up", "win", "lose", "click", "step")
MOODS = ("happy", "calm", "adventure", "spooky")
SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10), "pentatonic": (0, 2, 4, 7, 9)}


# ── making sounds ───────────────────────────────────────────────────────


def wave_value(shape, phase, rng):
    if shape == "square":
        return 1.0 if (phase % 1.0) < 0.5 else -1.0
    if shape == "triangle":
        p = phase % 1.0
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if shape == "noise":
        return rng.uniform(-1, 1)
    return math.sin(2 * math.pi * phase)


def sweep(start, end, seconds, shape="square", volume=0.5, attack=0.005, rng=None, vibrato=0.0):
    """A tone gliding from start Hz to end Hz, fading out."""
    rng = rng or random.Random(0)
    n = max(1, int(RATE * seconds))
    out, phase, held = [], 0.0, 0.0
    for i in range(n):
        t = i / n
        hz = start * (end / start) ** t if start > 0 and end > 0 else start + (end - start) * t
        if vibrato:
            hz *= 1 + vibrato * math.sin(2 * math.pi * 6 * i / RATE)
        phase += hz / RATE
        if shape == "noise":
            if int(phase) != int(phase - hz / RATE):
                held = rng.uniform(-1, 1)            # noise that has a pitch: a new value each period
            v = held
        else:
            v = wave_value(shape, phase, rng)
        envelope = min(1.0, i / max(1, attack * RATE)) * (1 - t) ** 1.5
        out.append(v * volume * envelope)
    return out


def note_hz(semitones_from_a4):
    return 440.0 * 2 ** (semitones_from_a4 / 12.0)


def make_sound(kind, pitch=1.0, length=1.0, seed=0):
    """The samples of a game sound of this kind; seed makes another one of the same kind."""
    rng = random.Random(zlib.crc32(("%s:%d" % (kind, seed)).encode()))
    vary = (lambda a, b: rng.uniform(a, b)) if seed else (lambda a, b: (a + b) / 2)
    p, L = pitch, length
    if kind == "jump":
        return sweep(vary(240, 330) * p, vary(600, 800) * p, vary(0.16, 0.24) * L, "square", 0.35)
    if kind == "coin":
        a = vary(900, 1050) * p
        return sweep(a, a, 0.06 * L, "square", 0.3) + sweep(a * 4 / 3, a * 4 / 3, vary(0.18, 0.28) * L, "square", 0.3)
    if kind == "laser":
        return sweep(vary(1100, 1500) * p, vary(220, 340) * p, vary(0.12, 0.2) * L, rng.choice(("square", "triangle")) if seed else "square", 0.3)
    if kind == "explosion":
        return sweep(vary(90, 140) * p, vary(30, 50) * p, vary(0.5, 0.8) * L, "noise", 0.6, rng=rng)
    if kind == "hit":
        return [a + b for a, b in zip(sweep(vary(300, 420) * p, vary(80, 120) * p, 0.14 * L, "square", 0.3),
                                      sweep(vary(800, 1200) * p, 200 * p, 0.14 * L, "noise", 0.25, rng=rng))]
    if kind == "power up":
        out = []
        base = vary(-10, -2)
        for step in (0, 4, 7, 12, 16):
            hz = note_hz(base + step) * p
            out += sweep(hz, hz * 1.02, 0.07 * L, "square", 0.28)
        return out
    if kind in ("win", "lose"):
        steps = (0, 4, 7, 12) if kind == "win" else (7, 6, 5, 0)
        out = []
        base = vary(-2, 3) if kind == "win" else vary(-9, -4)
        for n, step in enumerate(steps):
            hz = note_hz(base + step) * p
            seconds = (0.12 if n < len(steps) - 1 else 0.45) * L
            out += sweep(hz, hz if kind == "win" else hz * 0.97, seconds, "square", 0.3, vibrato=0.01 if n == len(steps) - 1 else 0)
        return out
    if kind == "click":
        return sweep(vary(900, 1300) * p, vary(700, 900) * p, 0.035 * L, "square", 0.3)
    if kind == "step":
        return sweep(vary(400, 700) * p, vary(150, 250) * p, 0.06 * L, "noise", 0.3, rng=rng)
    raise ValueError("no sound called %r" % kind)


def make_music(mood="happy", speed=1.0, seed=0, bars=8):
    """A short tune that loops: a melody over a bass, in a scale and pace that fit the mood."""
    rng = random.Random(zlib.crc32(("%s:%d" % (mood, seed)).encode()))
    scale, root, bpm, shape = {"happy": ("major", -9, 140, "square"), "calm": ("pentatonic", -12, 92, "triangle"),
                               "adventure": ("minor", -10, 124, "square"), "spooky": ("minor", -14, 80, "triangle")}[mood]
    steps = SCALES[scale]
    beat = 60.0 / (bpm * speed)
    chords = [0, 3, 4, 0] if scale != "pentatonic" else [0, 2, 3, 0]
    melody, bass = [], []
    degree = 0
    for bar in range(bars):
        chord = chords[bar % 4]
        for b in range(4):
            if rng.random() < 0.15 and b:
                melody += [0.0] * int(RATE * beat)
                continue
            degree = max(-3, min(9, degree + rng.choice((-2, -1, -1, 1, 1, 2, 0))))
            if b == 0:
                degree = chord + rng.choice((0, 2, 4)) if scale != "pentatonic" else chord + rng.choice((0, 2))
            octave, at = divmod(degree, len(steps))
            hz = note_hz(root + 12 + steps[at] + 12 * octave)
            melody += sweep(hz, hz, beat * 0.95, shape, 0.16, attack=0.01) + [0.0] * (int(RATE * beat) - int(RATE * beat * 0.95))
        octave, at = divmod(chord, len(steps))
        hz = note_hz(root - 12 + steps[at] + 12 * octave)
        for b in range(2):
            bass += sweep(hz, hz, beat * 1.9, "triangle", 0.22, attack=0.01) + [0.0] * (int(RATE * beat * 2) - int(RATE * beat * 1.9))
    n = min(len(melody), len(bass))
    return [melody[i] + bass[i] for i in range(n)]


def write_wav(path, samples):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples))


def make_recipe(folder):
    """The sounds a template asks for in its sounds.json ({"assets/jump.wav": {"sound": "jump", "seed": 1}, ...,
    {"music": "happy"}}), written where it says. The recipe goes once the sounds are there."""
    recipe = os.path.join(folder, "sounds.json")
    if not os.path.isfile(recipe):
        return []
    with open(recipe, encoding="utf-8") as fh:
        wanted = json.load(fh)
    made = []
    for rel, how in wanted.items():
        path = os.path.join(folder, *rel.split("/"))
        if os.path.exists(path):
            continue
        if "music" in how:
            samples = make_music(how["music"], how.get("speed", 1.0), how.get("seed", 0))
        else:
            samples = make_sound(how["sound"], how.get("pitch", 1.0), how.get("length", 1.0), how.get("seed", 0))
        write_wav(path, samples)
        made.append(rel)
    os.remove(recipe)
    return made
