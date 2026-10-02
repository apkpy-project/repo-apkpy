"""Draw the demo's pictures: a dusk scene with small details worth zooming
into, and three square ones. Nothing here is anybody's photograph."""
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

random.seed(7)


def font(size):
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()


def sky(width, height, top, bottom):
    image = Image.new("RGB", (width, height))
    px = image.load()
    for y in range(height):
        t = y / (height - 1)
        row = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(width):
            px[x, y] = row
    return image


def harbour():
    w, h = 1800, 1200
    image = sky(w, h, (24, 28, 72), (250, 150, 96))
    draw = ImageDraw.Draw(image)
    draw.ellipse((1180, 520, 1400, 740), fill=(255, 214, 150))
    # hills
    for base, colour in ((700, (58, 52, 96)), (760, (40, 38, 78))):
        points = [(0, h)]
        for x in range(0, w + 60, 60):
            points.append((x, base - 70 * math.sin(x / 190.0 + base) - random.randint(0, 30)))
        points.append((w, h))
        draw.polygon(points, fill=colour)
    # water
    draw.rectangle((0, 820, w, h), fill=(30, 40, 84))
    for y in range(830, h, 14):
        for _ in range(26):
            x = random.randint(0, w)
            draw.line((x, y, x + random.randint(20, 90), y), fill=(250, 170, 120), width=2)
    # town: small houses with lit windows -- the detail a zoom is for
    x = 80
    while x < w - 120:
        width, height = random.randint(46, 96), random.randint(50, 130)
        top = 820 - height
        draw.rectangle((x, top, x + width, 820), fill=(22, 22, 48))
        for wx in range(x + 8, x + width - 10, 16):
            for wy in range(top + 10, 810, 20):
                if random.random() < 0.6:
                    draw.rectangle((wx, wy, wx + 7, wy + 9), fill=(255, 216, 128))
        x += width + random.randint(4, 22)
    # boats and their names
    for i, name in enumerate(("Maré Alta", "Sardinha", "Vento Norte", "Luzia")):
        bx = 180 + i * 420
        by = 900 + (i % 2) * 70
        draw.polygon([(bx, by), (bx + 170, by), (bx + 140, by + 34), (bx + 26, by + 34)],
                     fill=(236, 232, 224))
        draw.line((bx + 84, by, bx + 84, by - 120), fill=(236, 232, 224), width=4)
        draw.polygon([(bx + 88, by - 116), (bx + 88, by - 20), (bx + 150, by - 20)],
                     fill=(214, 84, 70))
        draw.text((bx + 40, by + 8), name, fill=(40, 44, 80), font=font(15))
    draw.text((60, 1120), "Porto de abrigo, 19:42", fill=(255, 236, 214), font=font(34))
    return image.filter(ImageFilter.SMOOTH)


def square(top, bottom, shape):
    image = sky(900, 900, top, bottom)
    draw = ImageDraw.Draw(image)
    if shape == "sun":
        draw.ellipse((300, 260, 600, 560), fill=(255, 226, 150))
        draw.rectangle((0, 640, 900, 900), fill=(36, 60, 110))
    elif shape == "peak":
        draw.polygon([(60, 900), (430, 220), (560, 460), (680, 330), (880, 900)], fill=(46, 58, 84))
        draw.polygon([(430, 220), (380, 320), (480, 330)], fill=(240, 244, 250))
    else:
        for i in range(9):
            x = 60 + i * 96
            draw.rectangle((x, 380 - (i % 3) * 90, x + 70, 900), fill=(30, 30, 58))
            for wy in range(420 - (i % 3) * 90, 880, 34):
                draw.rectangle((x + 12, wy, x + 26, wy + 16), fill=(255, 214, 120))
    return image


harbour().save("harbour.jpg", quality=90)
square((255, 170, 120), (250, 110, 110), "sun").save("coast.jpg", quality=88)
square((120, 170, 230), (220, 232, 246), "peak").save("peak.jpg", quality=88)
square((30, 30, 70), (120, 70, 130), "city").save("city.jpg", quality=88)
print("pictures drawn")
