"""The pictures and three short tracks the replicas use, drawn here.

Nothing is downloaded: the covers, faces, photos and stories are gradients
with a title, and the tracks are a few seconds of synthesised tones.
"""
import math
import os
import random
import struct
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
# A bold sans for the titles drawn on the covers: whichever this system has.
FONTS = ("segoeuib.ttf", "C:/Windows/Fonts/segoeuib.ttf", "DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "Arial Bold.ttf")
random.seed(7)


def gradient(size, top, bottom, angle=False):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = ((x / w + y / h) / 2) if angle else y / h
            px[x, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img


def blobs(img, colours, count=6):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = img.size
    for _ in range(count):
        r = random.randint(w // 8, w // 3)
        x, y = random.randint(0, w), random.randint(0, h)
        c = random.choice(colours)
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (150,))
    layer = layer.filter(ImageFilter.GaussianBlur(w // 14))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def text(img, words, size, colour=(255, 255, 255), where="bottom"):
    d = ImageDraw.Draw(img)
    f = None
    for candidate in FONTS:
        try:
            f = ImageFont.truetype(candidate, size)
            break
        except OSError:
            continue
    if f is None:
        f = ImageFont.load_default(size)
    w, h = img.size
    box = d.textbbox((0, 0), words, font=f)
    x = (w - (box[2] - box[0])) // 2
    y = h - (box[3] - box[1]) - h // 10 if where == "bottom" else (h - (box[3] - box[1])) // 2
    d.text((x, y), words, font=f, fill=colour)
    return img


COVERS = [("Night Drive", (20, 20, 60), (200, 60, 140)),
          ("Lisbon Rain", (10, 40, 60), (40, 160, 170)),
          ("Neon Bloom", (60, 10, 60), (250, 120, 60)),
          ("Slow Tide", (5, 30, 40), (80, 200, 150)),
          ("Gold Hour", (70, 30, 5), (250, 200, 80)),
          ("Static Heart", (30, 30, 30), (150, 80, 240))]
for i, (name, a, b) in enumerate(COVERS, 1):
    img = blobs(gradient((400, 400), a, b, angle=True), [a, b, (255, 255, 255)])
    text(img, name, 44).save(os.path.join(HERE, f"cover{i}.png"))

for i, (a, b) in enumerate([((250, 180, 120), (60, 40, 90)), ((30, 120, 160), (230, 230, 200))], 1):
    img = blobs(gradient((800, 800), a, b), [a, b, (255, 255, 255)], 9)
    d = ImageDraw.Draw(img)
    if i == 1:   # a sun over hills
        d.ellipse((520, 140, 680, 300), fill=(255, 230, 170))
        d.polygon([(0, 800), (0, 560), (260, 470), (520, 600), (800, 500), (800, 800)], fill=(40, 30, 60))
    else:        # waves
        for k in range(6):
            y = 450 + k * 60
            d.arc((-100, y - 80, 900, y + 80), 180, 360, fill=(255, 255, 255), width=6)
    img.save(os.path.join(HERE, f"post{i}.jpg"), quality=88)

for i, (a, b) in enumerate([((120, 40, 160), (250, 150, 80)), ((10, 60, 90), (120, 220, 200)),
                            ((200, 40, 80), (40, 20, 80))], 1):
    img = blobs(gradient((720, 1280), a, b), [a, b, (255, 255, 255)], 10)
    text(img, ["Morning run", "Sea day", "Late set"][i - 1], 64, where="center")
    img.save(os.path.join(HERE, f"story{i}.jpg"), quality=86)

for i, (a, b) in enumerate([((250, 200, 150), (200, 120, 90)), ((150, 200, 250), (60, 90, 170)),
                            ((200, 250, 180), (60, 150, 90)), ((250, 180, 220), (170, 80, 150)),
                            ((240, 230, 160), (180, 130, 40))], 1):
    img = gradient((240, 240), a, b)
    d = ImageDraw.Draw(img)
    d.ellipse((75, 45, 165, 135), fill=(255, 240, 225))          # head
    d.ellipse((35, 150, 205, 320), fill=(255, 240, 225))         # shoulders
    img.save(os.path.join(HERE, f"face{i}.png"))


# Three short tunes, so the player has something real to play.
RATE = 22050
TUNES = [[0, 4, 7, 12, 7, 4, 0, -5], [0, 3, 7, 10, 12, 10, 7, 3], [0, 5, 9, 12, 9, 5, 2, 7]]
for n, tune in enumerate(TUNES, 1):
    frames = bytearray()
    base = 220.0 * (1.12 ** n)
    for bar in range(4):
        for step in tune:
            freq = base * 2 ** (step / 12)
            length = int(RATE * 0.45)
            for i in range(length):
                t = i / RATE
                env = min(1.0, i / 400) * math.exp(-3.2 * t)
                v = env * (0.55 * math.sin(2 * math.pi * freq * t) + 0.2 * math.sin(4 * math.pi * freq * t))
                frames += struct.pack("<h", int(v * 12000))
    with wave.open(os.path.join(HERE, f"track{n}.wav"), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(bytes(frames))
print("assets ok")
