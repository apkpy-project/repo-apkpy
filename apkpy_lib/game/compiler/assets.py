"""Asset processing at build time: atlases (Pillow) and desktop audio copies (ffmpeg).

Both tools come with ApkPy already (Pillow, imageio-ffmpeg).
"""
import os
import shutil
import subprocess

from ..errors import GameError

MAX_ATLAS = 2048
PAD = 2


def pack_atlas(project_root, atlas, out_png):
    """Packs atlas.files into one PNG (shelf packing). Answers [[x, y, w, h], ...] in file order."""
    from PIL import Image
    images = [Image.open(os.path.join(project_root, f)).convert("RGBA") for f in atlas.files]
    area = sum((i.width + PAD) * (i.height + PAD) for i in images)
    width = 64
    while width * width < area * 1.3 or width < max(i.width for i in images) + PAD:
        width *= 2
    order = sorted(range(len(images)), key=lambda k: -images[k].height)
    regions = [None] * len(images)
    x = y = shelf = 0
    for k in order:
        img = images[k]
        if x + img.width > width:
            x, y, shelf = 0, y + shelf + PAD, 0
        regions[k] = [x, y, img.width, img.height]
        x += img.width + PAD
        shelf = max(shelf, img.height)
    height = y + shelf
    if width > MAX_ATLAS or height > MAX_ATLAS:
        raise GameError("G1215", "the atlas %s would be %dx%d (more than %d)" % (atlas.pattern, width, height,
                                                                                 MAX_ATLAS),
                        fix="Split it into several atlases, or use smaller images.")
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for img, (rx, ry, _, _) in zip(images, regions):
        sheet.paste(img, (rx, ry))
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    sheet.save(out_png)
    return regions


def desktop_wav(source, cache_dir, rel):
    """A WAV copy for javax.sound (the desktop runner), cached by modification time. Answers its path."""
    out = os.path.join(cache_dir, "audio-desktop", rel + ".wav")
    if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(source):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if source.lower().endswith(".wav"):
        shutil.copy2(source, out)
        return out
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None                      # the desktop plays without it (a warning); the phone is not affected
    done = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", source, "-acodec", "pcm_s16le",
                           "-ar", "44100", out], capture_output=True)
    return out if done.returncode == 0 else None
