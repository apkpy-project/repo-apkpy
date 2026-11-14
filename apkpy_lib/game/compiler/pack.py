"""The bundle to game.aar: assets/apkpygame/** (and the translated code as classes.jar).

Written to build/apkpygame/apkpygame-game.aar in the project. The build of the app copies it, with the
engine's AAR, into the Android project's app/libs/, where the glue's Gradle lines read them. Audio is stored
uncompressed (AssetFileDescriptor needs it); audio-desktop/ stays out of the APK.
"""
import io
import os
import zipfile


MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="apkpygame.game">
    <uses-sdk android:minSdkVersion="24" />
</manifest>
"""
AAR = "apkpygame-game.aar"
STORED = (".ogg", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp")


def game_aar(project):
    os.makedirs(project.build_dir, exist_ok=True)
    out = os.path.join(project.build_dir, AAR)
    classes = io.BytesIO()
    game_jar = os.path.join(project.build_dir, "game.jar")
    if os.path.isfile(game_jar):                     # the translated scripts (compiler/javac.py)
        with open(game_jar, "rb") as fh:
            classes.write(fh.read())
    else:
        with zipfile.ZipFile(classes, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    count = 0
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("AndroidManifest.xml", MANIFEST)
        z.writestr("R.txt", "")
        z.writestr("classes.jar", classes.getvalue())
        # Game.load finds apkpygame.game.GameScripts by name: R8 must keep it
        z.writestr("proguard.txt", "-keep class apkpygame.game.** { *; }\n")
        for root, _, files in os.walk(project.bundle_dir):
            for name in sorted(files):
                path = os.path.join(root, name)
                rel = os.path.relpath(path, project.bundle_dir).replace("\\", "/")
                if rel.startswith("audio-desktop/"):
                    continue
                kind = zipfile.ZIP_STORED if name.lower().endswith(STORED) else zipfile.ZIP_DEFLATED
                z.write(path, "assets/apkpygame/" + rel, compress_type=kind)
                count += 1
    os.replace(tmp, out)
    return out, count
