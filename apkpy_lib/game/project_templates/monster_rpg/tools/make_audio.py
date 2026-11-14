"""Writes the template's placeholder music and sounds (original, synthesised here) into assets/.

    python tools/make_audio.py
"""
import math
import os
import struct
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
RATE = 22050
NOTES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def freq(note):
    return 220.0 * 2 ** ((NOTES[note[0]] + 12 * (int(note[1]) - 3) + 3 - 12) / 12.0)


def tone(hz, seconds, volume=0.2, shape="square"):
    n = int(RATE * seconds)
    out = []
    for i in range(n):
        t = i / RATE
        wave_value = (1 if math.sin(2 * math.pi * hz * t) > 0 else -1) if shape == "square" else math.sin(2 * math.pi * hz * t)
        out.append(wave_value * volume * min(1, (n - i) / (RATE * 0.03)))
    return out


def melody(text, beat):
    out = []
    for word in text.split():
        out += [0.0] * int(RATE * beat) if word == "-" else tone(freq(word), beat, 0.14)
    return out


def write(name, samples):
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    write("music_town.wav", melody("e4 g4 a4 g4 e4 d4 c4 d4 e4 - g4 e4 d4 - c4 - a3 c4 d4 e4 d4 c4 a3 - c4 e4 g4 e4 d4 - c4 -", 0.26))
    write("music_battle.wav", melody("a3 a3 e4 a3 c4 a3 e4 g4 a3 a3 e4 a3 d4 c4 b3 g3", 0.15) * 3)
    write("sfx_tap.wav", tone(880, 0.05, 0.25))
    write("sfx_hit.wav", tone(160, 0.12, 0.35))
    write("sfx_heal.wav", tone(660, 0.08, 0.25) + tone(880, 0.08, 0.25) + tone(1100, 0.14, 0.25))
    write("sfx_catch.wav", tone(440, 0.07, 0.25) + tone(660, 0.07, 0.25) + tone(880, 0.2, 0.25))
    print("audio written to", OUT)
