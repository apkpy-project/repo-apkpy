"""Build apkpy_lib/icon_data/material_icons.json.gz from Android Studio.

Android Studio's Vector Asset tool ships the Material Icons (Apache License
2.0) as VectorDrawable XML inside plugins/android/lib/android.jar -- the same
24x24 path data icons.py already holds for its 71 curated names. This reads
the filled and outlined families from there, with no download:

    python tools/build_icon_data.py ["C:\\Program Files\\Android\\Android Studio"]

Icons that need android:fillType="evenOdd" are left out: icons.py fills
nonZero, and would fill their holes.
"""
import gzip
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apkpy_lib" / "icon_data" / "material_icons.json.gz"
STUDIO = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Android\Android Studio")
JAR = STUDIO / "plugins" / "android" / "lib" / "android.jar"
FAMILIES = {"materialicons": "f", "materialiconsoutlined": "o"}


def main():
    jar = zipfile.ZipFile(JAR)
    data = {"f": {}, "o": {}, "tags": {}}
    skipped = []
    for entry in jar.namelist():
        parts = entry.split("/")
        if len(parts) != 6 or parts[:3] != ["images", "material", "icons"]:
            continue
        family = FAMILIES.get(parts[3])
        if family is None or not entry.endswith("_24.xml"):
            continue
        name = parts[4]
        xml = jar.read(entry).decode("utf-8")
        if "fillType" in xml or "fillAlpha" in xml or "<group" in xml:
            skipped.append(name)
            continue
        paths = re.findall(r'android:pathData="([^"]+)"', xml)
        if paths:
            data[family][name] = " ".join(p.strip() for p in paths)
    # Outlined only where it differs from filled: most icons are the same.
    data["o"] = {k: v for k, v in data["o"].items() if data["f"].get(k) != v}
    meta = json.loads(jar.read("images/material/icons/icons_metadata.txt").decode("utf-8"))
    for icon in meta.get("icons", []):
        if icon.get("name") in data["f"]:
            data["tags"][icon["name"]] = [t.lower() for t in icon.get("tags", [])][:8]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    # mtime=0: the same icons give the same bytes, so a rebuild is no change.
    with open(OUT, "wb") as target, gzip.GzipFile(
            filename="", mode="wb", fileobj=target, compresslevel=9, mtime=0) as fh:
        fh.write(raw)
    print(f"{len(data['f'])} filled, {len(data['o'])} outlined variants, "
          f"{len(set(skipped))} skipped -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
