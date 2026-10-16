import click
import os
import re
import sys
import zipfile
import shutil
import time
import runpy

from .core.compiler import translate_python_to_java, translate_python_to_android
from . import native_build as nb
from . import config as appconfig
from . import agents_guide
from .diagnostics import (
    Diagnostic, diagnose_build_failure, format_exception, render_diagnostic,
)


def _remove_tree(path, attempts=6):
    """Remove a generated project, retrying transient Windows file locks."""
    if not os.path.exists(path):
        return
    last_error = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.12 * (attempt + 1))
    raise last_error

def generate_gradle_files(base_path, package_name, project_name, needs_workmanager=False,
                           needs_recyclerview=False, needs_drawer=False,
                           needs_websocket=False,
                           needs_swiperefresh=False,
                           needs_media3=False, needs_firebase=False,
                          needs_location=False,
                          needs_biometric=False,
                          needs_billing=False,
                          needs_scan=False,
                          needs_camera=False,
                          google_services=False,
                          application_id=None,
                          version_code=1, version_name="1.0", signing=None,
                          extra_dependencies="", extra_keep=""):
    """
    Generates fundamental Gradle configuration files for an Android project.

    `package_name` is the internal namespace (the Java package, never changes).
    `application_id` is the Play Store id — it can differ from the namespace, and
    is what `apkpy.toml` lets the user customise. `version_code` / `version_name`
    also come from the config. `signing` (a dict from native_build.ensure_keystore)
    turns the release build into a SIGNED one — required for the Play Store.
    """
    application_id = application_id or package_name

    # native.gradle() e native.keep(): linhas que a app declarou no writehere.py
    # e que o transpilador deixou em native/gradle.txt e native/keep.pro.
    extra_dependencies_block = ""
    if extra_dependencies:
        extra_dependencies_block = "\n    " + "\n    ".join(
            line.strip() for line in str(extra_dependencies).splitlines()
            if line.strip())
    extra_keep_block = ""
    if extra_keep:
        extra_keep_block = "\n" + str(extra_keep).rstrip() + "\n"

    # Release signing — only when a keystore was provided (apkpy release).
    signing_block = ""
    buildtypes_block = ""
    if signing:
        ks_path = signing["keystore"].replace("\\", "/")
        signing_block = f"""
    signingConfigs {{
        release {{
            storeFile file('{ks_path}')
            storePassword '{signing["store_password"]}'
            keyAlias '{signing["key_alias"]}'
            keyPassword '{signing["key_password"]}'
        }}
    }}
"""
        buildtypes_block = """
    buildTypes {
        release {
            signingConfig signingConfigs.release
            // R8 keeps only the library code the app can actually
            // reach. A screen using two Material widgets was shipping
            // the whole of Material.
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'),
                    'proguard-rules.pro'
        }
    }
"""

    # Firebase Installations uses AndroidX DataStore. Its current Android
    # artifact includes a small native helper, so generated projects package
    # native libraries compressed. This avoids the
    # 16 KB page-size compatibility warning without changing non-Firebase
    # projects or forcing a broad AGP/Gradle upgrade.
    firebase_packaging_block = ""
    if needs_firebase:
        firebase_packaging_block = """
    packagingOptions {
        jniLibs {
            useLegacyPackaging true
        }
    }
"""
    app_dir = os.path.join(base_path, "app")
    os.makedirs(app_dir, exist_ok=True)

    # Shrinking and renaming are separate jobs, and only the first one is
    # wanted here. Renaming turns every class into a.b.c, which would make
    # crash.last() answer gibberish and force a mapping file to be kept for
    # the life of every published version. The saving is in the shrinking.
    proguard_rules = f"""# ApkPy: shrink, do not rename.
#
# -dontobfuscate keeps class and method names readable, so a crash report --
# including the one crash.last() hands back to the app -- still reads
# Screen_homeActivity.onCreate rather than a.b.c. Unused library code is
# still removed, which is where the size saving comes from.
-dontobfuscate

# Keep line numbers, so a stack trace still points at a real line.
-keepattributes SourceFile,LineNumberTable,*Annotation*,Signature

# The generated classes are reached from the manifest and from layouts,
# never from Java that R8 can follow.
-keep class {package_name}.** {{ *; }}
{extra_keep_block}"""
    with open(os.path.join(app_dir, "proguard-rules.pro"), "w",
              encoding="utf-8") as handle:
        handle.write(proguard_rules)
    
    settings_gradle_content = f"""pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}
rootProject.name = "{project_name}"
include ':app'
"""
    settings_path = os.path.join(base_path, "settings.gradle")
    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(settings_gradle_content)

    root_build_gradle_content = f"""plugins {{
    id 'com.android.application' version '8.6.1' apply false
{"    id 'org.jetbrains.kotlin.android' version '2.0.21' apply false" if needs_firebase else ""}
{"    id 'com.google.gms.google-services' version '4.5.0' apply false" if google_services else ""}
}}
"""
    root_build_path = os.path.join(base_path, "build.gradle")
    with open(root_build_path, "w", encoding="utf-8") as f:
        f.write(root_build_gradle_content)

    app_build_gradle_content = f"""plugins {{
    id 'com.android.application'
{"    id 'org.jetbrains.kotlin.android'" if needs_firebase else ""}
{"    id 'com.google.gms.google-services'" if google_services else ""}
}}

android {{
    namespace '{package_name}'
    compileSdk {appconfig.COMPILE_SDK}

    defaultConfig {{
        applicationId "{application_id}"
        minSdk {appconfig.MIN_SDK}
        targetSdk {appconfig.TARGET_SDK}
        versionCode {version_code}
        versionName "{version_name}"
    }}
{signing_block}{buildtypes_block}{firebase_packaging_block}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }}
}}

dependencies {{
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.11.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'{"" if not needs_workmanager else """
    implementation 'androidx.work:work-runtime:2.9.0'"""}{"" if not needs_recyclerview else """
    implementation 'androidx.recyclerview:recyclerview:1.3.2'"""}{"" if not needs_drawer else """
    implementation 'androidx.drawerlayout:drawerlayout:1.2.0'"""}{"" if not needs_websocket else """
    implementation 'com.squareup.okhttp3:okhttp:5.3.2'"""}{"" if not needs_swiperefresh else """
    implementation 'androidx.swiperefreshlayout:swiperefreshlayout:1.2.0'"""}{"" if not needs_media3 else """
    implementation 'androidx.media3:media3-exoplayer:1.3.1'
    implementation 'androidx.media3:media3-exoplayer-hls:1.3.1'
    implementation 'androidx.media3:media3-exoplayer-dash:1.3.1'
    implementation 'androidx.media3:media3-ui:1.3.1'"""}{"" if not needs_firebase else """
    implementation platform('com.google.firebase:firebase-bom:34.16.0')
    implementation 'com.google.firebase:firebase-messaging'"""}{"" if not needs_location else """
    implementation 'com.google.android.gms:play-services-location:21.3.0'"""}{"" if not needs_biometric else """
    implementation 'androidx.biometric:biometric:1.1.0'"""}{"" if not needs_billing else """
    implementation 'com.android.billingclient:billing:7.1.1'"""}{"" if not needs_scan else """
    implementation 'com.google.android.gms:play-services-code-scanner:16.1.0'"""}{"" if not needs_camera else """
    implementation 'androidx.camera:camera-camera2:1.4.2'
    implementation 'androidx.camera:camera-lifecycle:1.4.2'
    implementation 'androidx.camera:camera-view:1.4.2'
    implementation 'androidx.camera:camera-video:1.4.2'
    implementation 'androidx.exifinterface:exifinterface:1.3.7'"""}{extra_dependencies_block}
}}
"""
    app_build_path = os.path.join(app_dir, "build.gradle")
    with open(app_build_path, "w", encoding="utf-8") as f:
        f.write(app_build_gradle_content)

    # gradle.properties — required for AndroidX dependencies to work
    # The last line: this Android Gradle plugin was tested up to API 35 and
    # says so on every build, in words an app's author can do nothing about.
    # It builds against 36 all the same (checked: debug, release, R8); the
    # plugin that names 36 needs a newer Gradle than the one people have.
    gradle_properties_content = """android.useAndroidX=true
android.enableJetifier=true
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.overridePathCheck=true
android.suppressUnsupportedCompileSdk=%d
""" % appconfig.COMPILE_SDK
    gradle_properties_path = os.path.join(base_path, "gradle.properties")
    with open(gradle_properties_path, "w", encoding="utf-8") as f:
        f.write(gradle_properties_content)

    # gradle/wrapper/gradle-wrapper.properties pins the Gradle version required
    # by AGP 8.6. Gradle 9.x follows a separate compatibility schedule.
    wrapper_dir = os.path.join(base_path, "gradle", "wrapper")
    os.makedirs(wrapper_dir, exist_ok=True)
    gradle_wrapper_content = """distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""
    wrapper_path = os.path.join(wrapper_dir, "gradle-wrapper.properties")
    with open(wrapper_path, "w", encoding="utf-8") as f:
        f.write(gradle_wrapper_content)


_EXAMPLE_HELLO = '''\
from apkpy_lib import Screen, button, label, toast, run

main = Screen(id="main")

label("Welcome to ApkPy!", id="title", screen=main)
label("Your first app is ready.", id="subtitle", screen=main)

def on_press():
    toast("Hello, World!")

button("SAY HELLO", id="btn_hello", command=on_press, screen=main)

style = """
main {
    background-color: #1E293B;
}
title {
    color: #F8FAFC;
    font-size: 24px;
    font-weight: bold;
    margin-top: 40px;
}
subtitle {
    color: #94A3B8;
    font-size: 14px;
    margin-bottom: 24px;
}
btn_hello {
    background-color: #4F46E5;
    color: #F8FAFC;
    border-radius: 12px;
    font-size: 16px;
    font-weight: bold;
    padding: 14px;
    pressed-color: #3730A3;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_CALCULATOR = '''\
from apkpy_lib import Screen, button, label, inputs, run

main = Screen(id="main")

label("Calculator", id="title", screen=main)

num_a   = inputs("First number",  id="inp_a", screen=main)
num_b   = inputs("Second number", id="inp_b", screen=main)
result  = label("Result: —", id="lbl_result", screen=main)

def add():
    try:
        result.set_value(f"Result: {float(num_a.get_value()) + float(num_b.get_value())}")
    except Exception:
        result.set_value("Invalid numbers.")

def subtract():
    try:
        result.set_value(f"Result: {float(num_a.get_value()) - float(num_b.get_value())}")
    except Exception:
        result.set_value("Invalid numbers.")

def multiply():
    try:
        result.set_value(f"Result: {float(num_a.get_value()) * float(num_b.get_value())}")
    except Exception:
        result.set_value("Invalid numbers.")

def divide():
    try:
        b = float(num_b.get_value())
        result.set_value("Cannot divide by zero." if b == 0 else f"Result: {float(num_a.get_value()) / b}")
    except Exception:
        result.set_value("Invalid numbers.")

button("+ Add",      id="btn_add", command=add,      screen=main)
button("- Subtract", id="btn_sub", command=subtract, screen=main)
button("x Multiply", id="btn_mul", command=multiply, screen=main)
button("/ Divide",   id="btn_div", command=divide,   screen=main)

style = """
main { background-color: #0F172A; }
title {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: bold;
    margin-top: 28px;
    margin-bottom: 12px;
}
inp_a, inp_b {
    background-color: #1E293B;
    color: #F8FAFC;
    border-radius: 10px;
    border-color: #334155;
    border-width: 1px;
    font-size: 14px;
}
lbl_result {
    color: #38BDF8;
    font-size: 16px;
    font-weight: bold;
    margin-top: 8px;
    margin-bottom: 8px;
}
btn_add { background-color: #4F46E5; color: #F8FAFC; border-radius: 10px; padding: 12px; margin-top: 4px; pressed-color: #3730A3; }
btn_sub { background-color: #0891B2; color: #F8FAFC; border-radius: 10px; padding: 12px; margin-top: 4px; pressed-color: #0E7490; }
btn_mul { background-color: #059669; color: #F8FAFC; border-radius: 10px; padding: 12px; margin-top: 4px; pressed-color: #047857; }
btn_div { background-color: #DC2626; color: #F8FAFC; border-radius: 10px; padding: 12px; margin-top: 4px; pressed-color: #B91C1C; }
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_NOTES = '''\
from apkpy_lib import Screen, button, label, inputs, toast, storage, run

main = Screen(id="main")

label("My Notes", id="title", screen=main)

note_input = inputs("Write your note here...", id="inp_note", screen=main)
saved_lbl  = label("No saved note yet.", id="lbl_saved", screen=main)

saved = storage.get("note", "")
if saved != "":
    saved_lbl.set_value(f"Saved: {saved}")

def save_note():
    note = note_input.get_value()
    if note:
        storage.set("note", note)
        saved_lbl.set_value(f"Saved: {note}")
        toast("Note saved!")
    else:
        toast("Write something first.")

def clear_note():
    storage.delete("note")
    saved_lbl.set_value("No saved note yet.")
    note_input.set_value("")
    toast("Note cleared.")

button("SAVE NOTE",  id="btn_save",  command=save_note,  screen=main)
button("CLEAR NOTE", id="btn_clear", command=clear_note, screen=main)

style = """
main { background-color: #0F172A; }
title {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: bold;
    margin-top: 28px;
    margin-bottom: 12px;
}
inp_note {
    background-color: #1E293B;
    color: #F8FAFC;
    border-radius: 10px;
    border-color: #334155;
    border-width: 1px;
    focus-border-color: #818CF8;
    font-size: 14px;
    margin-bottom: 8px;
}
lbl_saved { color: #38BDF8; font-size: 13px; margin-bottom: 16px; }
btn_save {
    background-color: #4F46E5;
    color: #F8FAFC;
    border-radius: 12px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 6px;
    pressed-color: #3730A3;
}
btn_clear {
    background-color: #1E293B;
    color: #F87171;
    border-radius: 12px;
    font-size: 14px;
    padding: 14px;
    margin-top: 6px;
    border-color: #F87171;
    border-width: 1px;
    pressed-color: #0F172A;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_SETTINGS = '''\
from apkpy_lib import Screen, button, label, inputs, toast, storage, run

main = Screen(id="main")

label("Settings", id="title", screen=main)
status = label("—", id="status", screen=main)

chk_dark   = inputs("Dark mode",      id="chk_dark",   type="checkbox", screen=main)
chk_notif  = inputs("Notifications",  id="chk_notif",  type="checkbox", screen=main)
chk_sounds = inputs("Sound effects",  id="chk_sounds", type="checkbox", screen=main)
chk_auto   = inputs("Auto-save",      id="chk_auto",   type="checkbox", screen=main)

saved_dark   = storage.get("dark",   False)
saved_notif  = storage.get("notif",  True)
saved_sounds = storage.get("sounds", True)
saved_auto   = storage.get("auto",   True)

if saved_dark != "":   chk_dark.set_value(saved_dark)
if saved_notif != "":  chk_notif.set_value(saved_notif)
if saved_sounds != "": chk_sounds.set_value(saved_sounds)
if saved_auto != "":   chk_auto.set_value(saved_auto)

def save_settings():
    storage.set("dark",   chk_dark.get_value())
    storage.set("notif",  chk_notif.get_value())
    storage.set("sounds", chk_sounds.get_value())
    storage.set("auto",   chk_auto.get_value())
    status.set_value("Settings saved!")
    toast("Saved!")

button("SAVE SETTINGS", id="btn_save", command=save_settings, screen=main)

style = """
main { background-color: #0F172A; }
title {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: bold;
    margin-top: 28px;
    margin-bottom: 8px;
}
status { color: #38BDF8; font-size: 13px; margin-bottom: 8px; }
chk_dark, chk_notif, chk_sounds, chk_auto { color: #F8FAFC; margin-top: 4px; }
btn_save {
    background-color: #4F46E5;
    color: #F8FAFC;
    border-radius: 12px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 16px;
    pressed-color: #3730A3;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_LOGIN = '''\
from apkpy_lib import Screen, button, label, inputs, toast, run

login = Screen(id="login")
home  = Screen(id="home")

# ── Login Screen ──────────────────────────────────────────────────────
label("Welcome Back!", id="login_title", screen=login)
label("Sign in to continue.", id="login_sub", screen=login)

inp_user = inputs("Username", id="inp_user", screen=login)
inp_pass = inputs("Password", id="inp_pass", type="password", screen=login)

greeting = label("", id="greeting", screen=home)

def do_login():
    user = inp_user.get_value()
    pwd  = inp_pass.get_value()
    if user and pwd:
        greeting.set_value(f"Hello, {user}!")
    else:
        toast("Please fill in all fields.")

button("LOG IN",  id="btn_login",  command=do_login, on_click_navigate=home,  screen=login)
button("SIGN UP", id="btn_signup",                                              screen=login)

# ── Home Screen ───────────────────────────────────────────────────────
label("You\'re in!", id="home_title", screen=home)

button("LOG OUT", id="btn_logout", on_click_navigate=login, screen=home)

style = """
login, home { background-color: #0F172A; }

login_title {
    color: #F8FAFC;
    font-size: 26px;
    font-weight: bold;
    margin-top: 40px;
}
login_sub { color: #94A3B8; font-size: 13px; margin-bottom: 20px; }
greeting  { color: #38BDF8; font-size: 16px; margin-bottom: 16px; }

inp_user, inp_pass {
    background-color: #1E293B;
    color: #F8FAFC;
    border-radius: 10px;
    border-color: #334155;
    border-width: 1px;
    focus-border-color: #818CF8;
    font-size: 14px;
    margin-bottom: 8px;
}

btn_login {
    background-color: #4F46E5;
    color: #F8FAFC;
    border-radius: 12px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 8px;
    pressed-color: #3730A3;
}
btn_signup {
    background-color: #1E293B;
    color: #94A3B8;
    border-radius: 12px;
    font-size: 14px;
    padding: 14px;
    margin-top: 6px;
    border-color: #334155;
    border-width: 1px;
}

home_title {
    color: #F8FAFC;
    font-size: 26px;
    font-weight: bold;
    margin-top: 40px;
    margin-bottom: 20px;
}
btn_logout {
    background-color: #1E293B;
    color: #F87171;
    border-radius: 12px;
    font-size: 14px;
    padding: 14px;
    border-color: #F87171;
    border-width: 1px;
}
"""

if __name__ == "__main__":
    run(start_screen=login)
'''

_EXAMPLE_LOCATION = '''\
from apkpy_lib import Screen, label, button, toast, location, run

main = Screen(id="main")

label("Location / GPS Demo", id="title", screen=main)
coords = label("Location: unknown", id="coords", screen=main)
city   = label("City: -",           id="city",   screen=main)

# location.get_current() returns (success, lat, lng, city) asynchronously.
# lat/lng/city are strings; city comes from reverse geocoding the coordinates.
def on_location(success, lat, lng, city_name):
    if success:
        coords.set_value(f"Lat: {lat}, Lng: {lng}")
        city.set_value(f"City: {city_name}" if city_name else "City: (unknown)")
        toast("Location found!")
    else:
        coords.set_value("Location: unavailable")
        toast("Couldn't get your location.")

button("WHERE AM I?", id="btn_loc",
       command=lambda: location.get_current(on_result=on_location), screen=main)

style = """
main   { background-color: #0F172A; flex-direction: column; padding: 28px; gap: 12px; }
title  { color: #34D399; font-size: 22px; font-weight: bold; margin-top: 24px; }
coords { color: #38BDF8; font-size: 15px; font-weight: bold; }
city   { color: #A78BFA; font-size: 15px; font-weight: bold; margin-bottom: 6px; }
btn_loc { background-color: #059669; color: #ECFDF5; border-radius: 14px; font-weight: bold; padding: 14px; pressed-color: #047857; }
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_NETWORK_IMAGES = '''\
from apkpy_lib import Screen, label, image, run

main = Screen(id="main")

label("Network Images Demo", id="title", screen=main)
label("These images are downloaded from the internet at runtime.", id="subtitle", screen=main)

# image() accepts a URL — loaded at runtime in a background thread.
image("https://picsum.photos/600/300", id="banner", screen=main)
image("https://i.pravatar.cc/200",     id="avatar", screen=main)

style = """
main     { background-color: #0F172A; flex-direction: column; padding: 24px; gap: 16px; }
title    { color: #60A5FA; font-size: 22px; font-weight: bold; margin-top: 24px; }
subtitle { color: #94A3B8; font-size: 13px; margin-bottom: 8px; }
banner   { width: 300px; height: 150px; border-radius: 16px; }
avatar   { width: 120px; height: 120px; border-radius: 60px; border-color: #60A5FA; border-width: 3px; }
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_SPINNER = '''\
from apkpy_lib import Screen, label, button, spinner, https, json_get, run

main = Screen(id="main")

label("Loading Spinner Demo", id="title", screen=main)
result = label("Press FETCH to load data from the internet.", id="result", screen=main)

# Start hidden — only shown while the request is running.
loading = spinner(id="loading", screen=main, visible=False)

def on_response(success, response):
    loading.hide()
    if success:
        result.set_value("Title: " + json_get(response, "title"))
    else:
        result.set_value("Request failed.")

def fetch():
    loading.show()
    result.set_value("Loading...")
    https.get("https://jsonplaceholder.typicode.com/todos/1", on_response=on_response)

button("FETCH", id="btn", command=fetch, screen=main)

style = """
main    { background-color: #0F172A; flex-direction: column; padding: 28px; gap: 16px; }
title   { color: #818CF8; font-size: 22px; font-weight: bold; margin-top: 24px; }
result  { color: #E2E8F0; font-size: 14px; }
loading { color: #6366F1; width: 48px; height: 48px; }
btn     { background-color: #6366F1; color: #FFFFFF; border-radius: 14px; font-weight: bold; padding: 14px; pressed-color: #4338CA; }
"""

if __name__ == "__main__":
    run(start_screen=main)
'''

_EXAMPLE_SECURE_LOGIN = '''\
from apkpy_lib import Screen, label, inputs, button, toast, storage, crypto, run

login = Screen(id="login")

label("Secure Login", id="title", screen=login)
label("Password is stored as hash+salt, never plain text.", id="hint", screen=login)

pw_in  = inputs("Password", id="pw_in", type="password", screen=login)
status = label("No account yet - register first.", id="status", screen=login)

def register():
    senha = pw_in.get_value()
    # Stores "pbkdf2-sha256$200000$<salt>$<hash>" - PBKDF2 key stretching makes
    # GPU brute-force ~200,000x slower; decompiling the APK reveals nothing.
    storage.set("pw_hash", crypto.hash_password(senha))
    status.set_value("Account created. Now try LOGIN.")
    toast("Registered!")

def do_login():
    senha    = pw_in.get_value()
    guardado = storage.get("pw_hash", "")
    ok = crypto.verify_password(senha, guardado)
    if ok:
        status.set_value("Welcome back!")
        toast("Login OK!")
    else:
        status.set_value("Wrong password.")
        toast("Wrong password.")

button("REGISTER", id="btn_reg", screen=login, command=register)
button("LOGIN",    id="btn_log", screen=login, command=do_login)

style = """
login   { background-color: #0F172A; }
title   { color: #F8FAFC; font-size: 24px; font-weight: bold; margin-top: 24px; }
hint    { color: #94A3B8; font-size: 13px; }
pw_in   { color: #F8FAFC; background-color: #1E293B; border-radius: 10px; padding: 12px; margin-top: 16px; }
status  { color: #38BDF8; font-size: 15px; margin-top: 12px; }
btn_reg { color: #F8FAFC; background-color: #6366F1; border-radius: 10px; font-weight: bold; padding: 14px; margin-top: 16px; pressed-color: #4338CA; }
btn_log { color: #F8FAFC; background-color: #10B981; border-radius: 10px; font-weight: bold; padding: 14px; pressed-color: #047857; }
"""

if __name__ == "__main__":
    run(start_screen=login)
'''

_EXAMPLE_REST_CLIENT = '''\
from apkpy_lib import Screen, label, button, toast, https, json_get, run

# Full CRUD against any REST API: GET / POST / PUT / PATCH / DELETE.
# Demo uses jsonplaceholder.typicode.com (free fake API) - swap in your backend.

api = Screen(id="api")

label("REST Client", id="title", screen=api)
label("Full CRUD: GET - POST - PUT - PATCH - DELETE", id="hint", screen=api)
status   = label("Press a button to call the API.", id="status", screen=api)
body_lbl = label("(response will show here)", id="body_lbl", screen=api)

def show_read(ok, resp):
    if ok:
        titulo = json_get(resp, "title")
        status.set_value("Success!")
        body_lbl.set_value(f"title: {titulo}")
    else:
        status.set_value("Request failed.")
        body_lbl.set_value(resp)

def show_delete(ok, resp):
    if ok:
        status.set_value("DELETE - resource gone.")
        body_lbl.set_value("response: {} (deleted)")
    else:
        status.set_value("Request failed.")
        body_lbl.set_value(resp)

def do_get():
    toast("GET...")
    https.get("https://jsonplaceholder.typicode.com/posts/1", on_response=show_read)

def do_post():
    toast("POST...")
    https.post("https://jsonplaceholder.typicode.com/posts",
               '{"title": "created by ApkPy", "body": "hello", "userId": 1}',
               headers={"Content-Type": "application/json"},
               on_response=show_read)

def do_put():
    toast("PUT...")
    https.put("https://jsonplaceholder.typicode.com/posts/1",
              '{"id": 1, "title": "replaced by ApkPy", "body": "full", "userId": 1}',
              headers={"Content-Type": "application/json"},
              on_response=show_read)

def do_patch():
    toast("PATCH...")
    https.patch("https://jsonplaceholder.typicode.com/posts/1",
                '{"title": "patched by ApkPy"}',
                headers={"Content-Type": "application/json"},
                on_response=show_read)

def do_delete():
    toast("DELETE...")
    https.delete("https://jsonplaceholder.typicode.com/posts/1", on_response=show_delete)

button("GET",    id="btn_get",    screen=api, command=do_get)
button("POST",   id="btn_post",   screen=api, command=do_post)
button("PUT",    id="btn_put",    screen=api, command=do_put)
button("PATCH",  id="btn_patch",  screen=api, command=do_patch)
button("DELETE", id="btn_delete", screen=api, command=do_delete)

style = """
api      { background-color: #0F172A; }
title    { color: #F8FAFC; font-size: 22px; font-weight: bold; margin-top: 20px; }
hint     { color: #94A3B8; font-size: 13px; }
status   { color: #38BDF8; font-size: 15px; margin-top: 12px; }
body_lbl { color: #F59E0B; font-size: 12px; }
btn_get    { color: #F8FAFC; background-color: #10B981; border-radius: 10px; font-weight: bold; padding: 12px; margin-top: 12px; pressed-color: #047857; }
btn_post   { color: #F8FAFC; background-color: #6366F1; border-radius: 10px; font-weight: bold; padding: 12px; pressed-color: #4338CA; }
btn_put    { color: #F8FAFC; background-color: #F59E0B; border-radius: 10px; font-weight: bold; padding: 12px; pressed-color: #B45309; }
btn_patch  { color: #0F172A; background-color: #38BDF8; border-radius: 10px; font-weight: bold; padding: 12px; pressed-color: #0369A1; }
btn_delete { color: #F8FAFC; background-color: #EF4444; border-radius: 10px; font-weight: bold; padding: 12px; pressed-color: #B91C1C; }
"""

if __name__ == "__main__":
    run(start_screen=api)
'''

_EXAMPLE_DB_NOTES_LIST = '''\
from apkpy_lib import Screen, label, button, inputs, list_view, toast, db, run

# The "data -> UI" pattern: db.query() JSON goes straight into a list_view.
# title= / subtitle= pick which field of each row to display.

notes = Screen(id="notes", scroll=True)

label("My Notes", id="title", screen=notes)
label("SQLite -> list_view, fully dynamic", id="hint", screen=notes)

note_in = inputs("Write a note...", id="note_in", screen=notes)
notes_list = list_view([], id="notes_list", screen=notes)

db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, created TEXT)")

def refresh():
    rows = db.query("SELECT content, created FROM notes ORDER BY id DESC")
    notes_list.set_items(rows, title="content", subtitle="created")

def add_note():
    texto = note_in.get_value()
    if texto:
        db.execute("INSERT INTO notes (content, created) VALUES (?, datetime('now'))", [texto])
        note_in.set_value("")
        refresh()
        toast("Note saved!")
    else:
        toast("Write something first.")

def clear_all():
    db.execute("DELETE FROM notes")
    refresh()
    toast("All notes deleted.")

button("ADD NOTE",  id="btn_add",     screen=notes, command=add_note)
button("REFRESH",   id="btn_refresh", screen=notes, command=refresh)
button("CLEAR ALL", id="btn_clear",   screen=notes, command=clear_all)

refresh()  # module-level: the list is filled on app start

style = """
notes      { background-color: #0F172A; }
title      { color: #F8FAFC; font-size: 22px; font-weight: bold; margin-top: 20px; }
hint       { color: #94A3B8; font-size: 13px; }
note_in    { color: #F8FAFC; background-color: #1E293B; border-radius: 10px; padding: 12px; margin-top: 12px; }
notes_list { background-color: #1E293B; color: #F8FAFC; border-color: #334155; margin-top: 12px; }
btn_add     { color: #F8FAFC; background-color: #10B981; border-radius: 10px; font-weight: bold; padding: 12px; margin-top: 12px; pressed-color: #047857; }
btn_refresh { color: #F8FAFC; background-color: #6366F1; border-radius: 10px; font-weight: bold; padding: 12px; pressed-color: #4338CA; }
btn_clear   { color: #F8FAFC; background-color: #EF4444; border-radius: 10px; font-weight: bold; padding: 12px; pressed-color: #B91C1C; }
"""

if __name__ == "__main__":
    run(start_screen=notes)
'''

_EXAMPLES = {
    1: ("Hello World",     _EXAMPLE_HELLO),
    2: ("Calculator",      _EXAMPLE_CALCULATOR),
    3: ("Notes",           _EXAMPLE_NOTES),
    4: ("Settings",        _EXAMPLE_SETTINGS),
    5: ("Login Screen",    _EXAMPLE_LOGIN),
    6: ("Location / GPS",  _EXAMPLE_LOCATION),
    7: ("Network Images",  _EXAMPLE_NETWORK_IMAGES),
    8: ("Loading Spinner", _EXAMPLE_SPINNER),
    9: ("Secure Login",    _EXAMPLE_SECURE_LOGIN),
    10: ("REST Client",    _EXAMPLE_REST_CLIENT),
    11: ("DB Notes List",  _EXAMPLE_DB_NOTES_LIST),
}


@click.group()
def main():
    """APKPy: Transform Python into Android Projects (APK)"""
    # Windows consoles default to cp1252, which can't encode the em dashes /
    # emoji we print and would crash with UnicodeEncodeError. UTF-8 is safe.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


@main.command()
def examples():
    """Choose a ready-made example app and drop it into any folder."""
    click.echo("")
    click.echo("What example do you want to use?")
    click.echo("")
    for num, (name, _) in _EXAMPLES.items():
        click.echo(f"  [{num}] {name}")
    click.echo("")

    choice = click.prompt("Enter a number", type=click.IntRange(1, len(_EXAMPLES)))
    example_name, code = _EXAMPLES[choice]

    path = click.prompt("\nWhere do you want to create it?", default=".")
    writehere_path = os.path.join(path, "writehere.py")

    if os.path.exists(writehere_path):
        answer = click.prompt(
            f'\n"writehere.py" already exists at that location. Overwrite it? (y/n)',
            default="n"
        )
        if answer.strip().lower() != "y":
            click.echo("Ok, we didn't create anything.")
            return
    else:
        answer = click.prompt(
            f'\nIt seems you don\'t have "writehere.py" here. Do you want to create it? (y/n)',
            default="y"
        )
        if answer.strip().lower() != "y":
            click.echo("Ok, we didn't create anything.")
            return

    os.makedirs(path, exist_ok=True)
    with open(writehere_path, "w", encoding="utf-8") as f:
        f.write(code)

    click.echo(f'\nDone! "{example_name}" example created at:')
    click.echo(f'  {os.path.abspath(writehere_path)}')
    _write_agent_files(path)
    click.echo(f'\nPreview it with:  python writehere.py')
    click.echo(f'Build it with:    apkpy build')


@main.command()
@click.argument('name')
def start(name):
    """Creates a new project: apkpy start my_project"""
    click.echo(f"Creating project: {name}...")

    current_dir  = os.getcwd()
    project_path = os.path.join(current_dir, name)

    if not os.path.exists(project_path):
        os.makedirs(project_path)
        with open(os.path.join(project_path, "writehere.py"), "w") as f:
            f.write(
                "from apkpy_lib.ui import Screen, button, label, inputs, run\n\n"
                "# --- Start Screen ---\n"
                "home = Screen(id=\"home\")\n"
                "label(\"Hello, ApkPy!\", screen=home)\n"
                "button(\"Continue\", screen=home)\n\n"
                "run(start_screen=home)\n"
            )
        _write_agent_files(project_path)
        click.echo(f"Success! Enter the '{name}' folder and edit writehere.py")
    else:
        click.echo("Error: This folder already exists.")


def _xml_escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
                  .replace('>', '&gt;').replace('"', '&quot;'))


def _apply_app_icon(build_dir, icon_path):
    """Gera o ícone da app (mipmap) em todas as densidades a partir de um PNG
    quadrado. Precisa de Pillow; se não estiver instalado, avisa e segue com o
    ícone padrão. Devolve True se gerou. Pós-processamento — não toca no transpilador."""
    try:
        from PIL import Image
    except ImportError:
        click.echo("   [WARNING]  Pillow não instalado (pip install Pillow) — a app fica com o ícone padrão.")
        return False
    try:
        img = Image.open(icon_path).convert("RGBA")
    except Exception as e:
        click.echo(f"   [WARNING]  não consegui abrir o ícone ({e}) — ícone padrão.")
        return False
    densities = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    res_dir = os.path.join(build_dir, "app/src/main/res")
    for dens, size in densities.items():
        mip_dir = os.path.join(res_dir, f"mipmap-{dens}")
        os.makedirs(mip_dir, exist_ok=True)
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(mip_dir, "ic_launcher.png"))
        resized.save(os.path.join(mip_dir, "ic_launcher_round.png"))
    click.echo(f"   [OK]  app icon generated (5 densities) from {os.path.basename(icon_path)}")
    return True


def _apply_app_config(build_dir, config, has_icon=False):
    """Aplica o nome (e, se houver, o ícone) ao AndroidManifest gerado, e remove
    o atributo `package=` deprecado (o namespace vai no build.gradle — isto
    silencia o aviso do AGP). Tudo pós-processamento, sem mexer no transpilador."""
    manifest_path = os.path.join(build_dir, "app/src/main/AndroidManifest.xml")
    if not os.path.exists(manifest_path):
        return
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = f.read()

    # 1. Remover package="..." do <manifest> (deprecado pelo AGP).
    manifest = re.sub(r'\s*package="[^"]*"', '', manifest, count=1)

    # 2. Nome da app → android:label.
    name = _xml_escape(config.get("name") or "ApkPy App")
    manifest = re.sub(r'android:label="[^"]*"', f'android:label="{name}"', manifest, count=1)

    # 3. Ícone (só se foi mesmo gerado) → android:icon / android:roundIcon.
    if has_icon and "android:icon=" not in manifest:
        manifest = manifest.replace(
            f'android:label="{name}"',
            f'android:label="{name}"\n        android:icon="@mipmap/ic_launcher"'
            f'\n        android:roundIcon="@mipmap/ic_launcher_round"',
            1,
        )

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest)


def _generate_android_project(python_code, build_dir, app_name, config=None, signing=None):
    """Transpile writehere.py and assemble a full, buildable Gradle project in build_dir.

    Shared by `apkpy build` (which then zips it) and `apkpy run` (which then
    compiles it into an APK). Returns the multi_files dict so callers can tell
    whether the multi-screen path ran (and whether WorkManager is needed).
    """
    template_path = os.path.join(os.path.dirname(__file__), "templates/android_project")

    # ── Try Multi-Screen mode first ──────────────────────────────────────────
    multi_files = translate_python_to_android(python_code)

    if multi_files and "error.txt" in multi_files:
        raise click.ClickException("\n" + multi_files["error.txt"].rstrip())

    if multi_files and "error.txt" not in multi_files:
        click.echo("Multi-Screen Mode detected — generating separate Activities...")

        if os.path.exists(build_dir):
            _remove_tree(build_dir)
        shutil.copytree(template_path, build_dir)

        java_dir     = os.path.join(build_dir, "app/src/main/java/com/apkpy/app")
        layout_dir   = os.path.join(build_dir, "app/src/main/res/layout")
        drawable_dir = os.path.join(build_dir, "app/src/main/res/drawable")
        anim_dir     = os.path.join(build_dir, "app/src/main/res/anim")
        os.makedirs(java_dir,   exist_ok=True)
        os.makedirs(layout_dir, exist_ok=True)
        os.makedirs(drawable_dir, exist_ok=True)
        os.makedirs(anim_dir, exist_ok=True)

        for rel_path, content in multi_files.items():
            if rel_path.startswith("java/"):
                out = os.path.join(java_dir, os.path.basename(rel_path))
            elif rel_path.startswith("res/"):
                # Preserve every Android resource qualifier (layout-land,
                # layout-sw600dp, values-night, etc.) instead of maintaining a
                # fragile allow-list of the unqualified resource folders.
                out = os.path.join(build_dir, "app/src/main", *rel_path.split('/'))
            elif rel_path == "AndroidManifest.xml":
                out = os.path.join(build_dir, "app/src/main/AndroidManifest.xml")
            else:
                out = os.path.join(build_dir, rel_path)

            os.makedirs(os.path.dirname(out), exist_ok=True)

            if isinstance(content, tuple) and content[0] == "COPY_FILE":
                source_path = content[1]
                if os.path.exists(source_path):
                    shutil.copyfile(source_path, out)
                    click.echo(f"   [OK]  {os.path.basename(out)} (copied from {source_path})")
                else:
                    click.echo(f"   [WARNING]  Image not found: {source_path}")
            else:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(content)
                click.echo(f"   [OK]  {os.path.basename(out)}")

    else:
        # ── Fallback: Single-Screen (MainActivity) ────────────────────────────
        click.echo("Single-Screen Mode — generating MainActivity...")

        java_code, drawables = translate_python_to_java(python_code)

        if "APKPY_DIAGNOSTIC" in java_code:
            readable = "\n".join(
                line.replace("        // ", "", 1)
                for line in java_code.splitlines()
                if "APKPY_DIAGNOSTIC" not in line
            ).strip()
            raise click.ClickException("\n" + readable)

        if os.path.exists(build_dir):
            _remove_tree(build_dir)
        shutil.copytree(template_path, build_dir)

        drawable_dir = os.path.join(build_dir, "app/src/main/res/drawable")
        if drawables:
            os.makedirs(drawable_dir, exist_ok=True)
            for path, content in drawables.items():
                out = os.path.join(build_dir, "app/src/main", path)
                with open(out, "w", encoding="utf-8") as f:
                    f.write(content)
                click.echo(f"   [OK]  {os.path.basename(out)}")

        main_activity_path = os.path.join(
            build_dir,
            "app/src/main/java/com/exemplo/MainActivity.java"
        )
        with open(main_activity_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content.replace("// INJECT_CODE_HERE", java_code)

        with open(main_activity_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    needs_workmanager = bool(multi_files) and any(k.endswith("Worker.java") for k in multi_files)
    needs_recyclerview = bool(multi_files) and any(
        isinstance(content, str)
        and "androidx.recyclerview.widget.RecyclerView" in content
        for content in multi_files.values()
    )
    needs_drawer = bool(multi_files) and any(
        isinstance(content, str)
        and "androidx.drawerlayout.widget.DrawerLayout" in content
        for content in multi_files.values()
    )
    needs_websocket = bool(multi_files) and any(
        isinstance(content, str)
        and "okhttp3.WebSocket" in content
        for content in multi_files.values()
    )
    needs_swiperefresh = bool(multi_files) and any(
        isinstance(content, str)
        and "androidx.swiperefreshlayout.widget.SwipeRefreshLayout" in content
        for content in multi_files.values()
    )
    needs_media3 = bool(multi_files) and any(
        isinstance(content, str)
        and "androidx.media3.ui.PlayerView" in content
        for content in multi_files.values()
    )
    needs_firebase = bool(multi_files) and any(
        isinstance(content, str)
        and "FirebaseMessagingService" in content
        for content in multi_files.values()
    )
    needs_location = bool(multi_files) and any(
        isinstance(content, str)
        and "FusedLocationProviderClient" in content
        for content in multi_files.values()
    )
    needs_biometric = bool(multi_files) and any(
        isinstance(content, str)
        and "androidx.biometric.BiometricPrompt" in content
        for content in multi_files.values()
    )
    needs_billing = bool(multi_files) and any(
        isinstance(content, str)
        and "com.android.billingclient.api.BillingClient" in content
        for content in multi_files.values()
    )
    needs_scan = bool(multi_files) and any(
        isinstance(content, str)
        and "com.google.mlkit.vision.codescanner" in content
        for content in multi_files.values()
    )
    google_services = False
    if needs_firebase:
        firebase_config = os.path.join(os.getcwd(), "google-services.json")
        if os.path.isfile(firebase_config):
            shutil.copy2(
                firebase_config,
                os.path.join(build_dir, "app", "google-services.json"),
            )
            google_services = True
            click.echo("   [OK]  Firebase configuration: google-services.json")
        else:
            click.echo(
                "   [WARN] Remote push is not configured: google-services.json "
                "was not found beside writehere.py. Preview simulation still "
                "works, but tokens, topics and real messages stay disabled."
            )

    # ── App config (apkpy.toml): nome, ícone, applicationId, versão ──────────
    config = config or appconfig.default_config()
    has_icon = _apply_app_icon(build_dir, config["icon"]) if config.get("icon") else False
    _apply_app_config(build_dir, config, has_icon=has_icon)

    generate_gradle_files(
        build_dir, appconfig.INTERNAL_NAMESPACE, app_name,
        needs_workmanager=needs_workmanager,
        needs_recyclerview=needs_recyclerview,
        needs_drawer=needs_drawer,
        needs_websocket=needs_websocket,
        needs_swiperefresh=needs_swiperefresh,
        needs_media3=needs_media3,
        needs_firebase=needs_firebase,
        needs_location=needs_location,
        needs_biometric=needs_biometric,
        needs_billing=needs_billing,
        needs_scan=needs_scan,
        needs_camera=bool(multi_files) and "java/ApkpyCameraActivity.java" in multi_files,
        extra_dependencies=(multi_files or {}).get("native/gradle.txt", ""),
        extra_keep=(multi_files or {}).get("native/keep.pro", ""),
        google_services=google_services,
        application_id=config.get("application_id"),
        version_code=config.get("version_code", 1),
        version_name=config.get("version_name", "1.0"),
        signing=signing,
    )
    return multi_files


def _sanitize_name(s):
    """Turn an arbitrary string into a safe project / output-file name."""
    s = (s or "").lstrip('﻿\xef\xbb\xbf﻿').strip()
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s).strip('_')
    return s or "app"


def _read_writehere():
    """Return the contents of writehere.py, or None (after printing) if absent."""
    if not os.path.exists("writehere.py"):
        error = FileNotFoundError(2, "writehere.py was not found", "writehere.py")
        click.echo(format_exception(error, context="Project source"), err=True)
        return None
    with open("writehere.py", "r", encoding="utf-8") as f:
        return f.read()


def _load_or_prompt_config(name=None):
    """Load apkpy.toml. If there's none (and no --name was given), ASK the user
    for the app name and save it to a fresh apkpy.toml — so the name is always a
    choice, never silently guessed. Returns the resolved config dict."""
    config = appconfig.load_config(".")
    for w in config.get("_warnings", []):
        click.echo(f"   [config]  {w}")

    if not config.get("_found") and not name:
        chosen = click.prompt("No apkpy.toml found. What should your app be called?",
                              default=config["name"])
        appconfig.write_scaffold(".", name=chosen)
        click.echo(f"Created {appconfig.CONFIG_FILENAME} — edit it anytime to set the icon, "
                   f"package id and version.")
        config = appconfig.load_config(".")

    if config.get("_found"):
        click.echo(f"Using apkpy.toml — {config['name']} "
                   f"(id: {config['application_id']}, v{config['version_name']})")
    return config


def _toolchain_help(tc):
    jdk_state = (
        "installed (Java %s)" % tc["jdk_major"]
        if tc["jdk_home"] else "missing"
    )
    if (not tc["jdk_home"] and tc["system_java"]
            and tc["system_java"] > nb.JDK_MAX):
        jdk_state = "system Java %s is too new" % tc["system_java"]
    diagnostic = Diagnostic(
        code="B5001",
        title="The Android build toolchain is incomplete",
        message="ApkPy cannot build the APK until the missing tools are installed.",
        context="Android APK build",
        received=(
            "JDK: %s; Android SDK: %s; Gradle %s: %s"
            % (
                jdk_state,
                "installed" if tc["sdk"] else "missing",
                nb.GRADLE_VERSION,
                "installed" if tc["gradle"] else "missing",
            )
        ),
        expected="JDK 17-21, an Android SDK and the supported Gradle version.",
        cause=(
            "`apkpy run` compiles the generated project itself, which needs a "
            "real Android toolchain on this machine. `apkpy build` only writes "
            "the project, so it works without one. A system Java newer than 21 "
            "does not count: Gradle 8.7 refuses to run on it."
        ),
        suggestions=[
            "Run `apkpy setup` to install the missing tools automatically.",
            "Run `apkpy doctor` afterwards to verify the installation.",
            "You can still run `apkpy build` and open the generated project in Android Studio.",
        ],
        docs="https://repo-apkpy.pages.dev/friendly-errors/#b5001-android-build",
    )
    click.echo(render_diagnostic(diagnostic))


@main.command()
@click.option('--debug', is_flag=True, help="Include the complete Python traceback.")
def preview(debug):
    """Open writehere.py with ApkPy's friendly startup diagnostics."""
    source_path = os.path.abspath("writehere.py")
    if not os.path.exists(source_path):
        error = FileNotFoundError(2, "writehere.py was not found", source_path)
        raise click.ClickException(
            "\n" + format_exception(error, context="Previewer startup").rstrip()
        )
    if debug:
        os.environ["APKPY_DEBUG"] = "1"
    try:
        runpy.run_path(source_path, run_name="__main__")
    except KeyboardInterrupt:
        return
    except SystemExit:
        raise
    except Exception as error:
        raise click.ClickException(
            "\n" + format_exception(
                error, context="Previewer startup", filename=source_path,
            ).rstrip()
        )


@main.command()
def build():
    """Compiles the code and generates a ZIP ready for Android Studio"""
    config = _load_or_prompt_config()
    app_name = _sanitize_name(config["name"])

    python_code = _read_writehere()
    if python_code is None:
        return

    build_dir = "build_temp"
    _generate_android_project(python_code, build_dir, app_name, config=config)
    shutil.make_archive(app_name, 'zip', build_dir)
    _remove_tree(build_dir)

    click.echo(f"\nSuccess! '{app_name}.zip' file generated.")
    click.echo("     Now just extract and open it in Android Studio.")


@main.command()
def init():
    """Create an apkpy.toml here — set the app's name, package id, version & icon."""
    path = appconfig.CONFIG_FILENAME
    if os.path.exists(path):
        click.echo(f"{path} already exists — leaving it untouched.")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(appconfig.scaffold_text("."))
        click.echo(f"Created {path}.")
        click.echo("Edit it to set your app name, Play Store package id, version and icon —")
        click.echo("then `apkpy run` / `apkpy build` will pick it up automatically.")
    _write_agent_files(".")


@main.command()
@click.option('--force', is_flag=True,
              help="Replace AGENTS.md and CLAUDE.md even if they were edited.")
def agents(force):
    """Write AGENTS.md here, so AI coding assistants know how ApkPy works."""
    _write_agent_files(".", force=force, explain=True)


def _write_agent_files(directory, force=False, explain=False):
    """AGENTS.md (and a CLAUDE.md pointing at it) beside writehere.py.

    No language model knows ApkPy from its training, so each project tells
    the assistant working in it. A file the person wrote or edited is kept.
    """
    try:
        results = agents_guide.write(directory, force=force)
    except OSError as exc:
        click.echo(f"Could not write {agents_guide.AGENTS_FILE}: {exc}")
        return
    for filename, outcome in results:
        if outcome == "kept":
            if filename == agents_guide.AGENTS_FILE:
                click.echo(f"{filename} was edited here — left as it is "
                           "(`apkpy agents --force` replaces it).")
            else:
                click.echo(f"{filename} is your own — left as it is. Add the line "
                           "`@AGENTS.md` to it so Claude Code reads the ApkPy guide.")
        elif outcome != "up to date" or explain:
            click.echo(f"{filename}: {outcome}.")
    if explain or any(o == "created" for f, o in results if f == agents_guide.AGENTS_FILE):
        click.echo("AGENTS.md tells AI coding assistants (Codex, Cursor, Copilot, "
                   "Claude Code...) how ApkPy works, so they write code that builds.")


@main.command()
@click.option('--name', default=None, help="App name (default: this folder's name).")
@click.option('--qr', is_flag=True, help="Also serve the APK over Wi-Fi with a QR code to install.")
@click.option('--usb', is_flag=True, help="Also install on a USB-connected device via adb.")
@click.option('--release', is_flag=True, help="Build an (unsigned) release APK instead of debug.")
def run(name, qr, usb, release):
    """Compile writehere.py straight into an installable .apk — no Android Studio."""
    python_code = _read_writehere()
    if python_code is None:
        return

    config = _load_or_prompt_config(name)
    if name:
        config["name"] = name   # --name wins for both the apk filename and the label
    app_name = _sanitize_name(name or config["name"])

    # 1) Find a usable toolchain (JDK 17-21 + SDK + Gradle).
    tc = nb.discover_toolchain()
    if not (tc['jdk_home'] and tc['sdk'] and tc['gradle']):
        _toolchain_help(tc)
        return
    click.echo(f"Toolchain OK — JDK {tc['jdk_major']}, Android SDK, Gradle {nb.GRADLE_VERSION}.")

    # 2) Generate the native project under ~/.apkpy/build so the user's folder stays clean.
    build_dir = os.path.join(nb.apkpy_home(), "build", app_name)
    os.makedirs(os.path.dirname(build_dir), exist_ok=True)
    _generate_android_project(python_code, build_dir, app_name, config=config)
    nb.write_local_properties(build_dir, tc['sdk'])

    # 3) Compile.
    click.echo("\nCompiling the APK with Gradle (the first build is slower)...\n")
    gradle_output = []
    if not nb.gradle_assemble(build_dir, tc['jdk_home'], tc['sdk'], tc['gradle'],
                              release=release, capture=gradle_output):
        click.echo(render_diagnostic(diagnose_build_failure(
            "\n".join(gradle_output),
            task="assembleRelease" if release else "assembleDebug",
            project_dir=build_dir,
        )))
        return
    apk = nb.find_built_apk(build_dir, release=release)
    if not apk:
        click.echo("Gradle reported success but no .apk was produced.")
        return

    # 4) The .apk always lands next to the user — QR/USB are just conveniences.
    suffix = "release" if release else "debug"
    dest = os.path.abspath(f"{app_name}-{suffix}.apk")
    shutil.copyfile(apk, dest)
    click.echo(f"\nAPK ready:  {dest}  ({os.path.getsize(dest) // 1024} KB)")

    # 5) Optional USB install.
    if usb:
        devices = nb.adb_devices(tc['sdk']) or []
        if not devices:
            click.echo("USB: no device detected (enable USB debugging) — skipping install.")
        else:
            click.echo(f"USB: installing on {devices[0]}...")
            ok, log = nb.adb_install(tc['sdk'], dest)
            click.echo("USB: installed!" if ok else f"USB: install failed —\n{log}")

    # 6) Optional QR / Wi-Fi install.
    if qr:
        try:
            httpd, url = nb.make_apk_server(dest)
        except OSError as e:
            click.echo(f"QR: couldn't start the local server ({e}).")
            return
        click.echo("\nScan to install on your phone (same Wi-Fi network):\n")
        if not nb.print_qr(url):
            click.echo("   (run 'pip install qrcode' to show a scannable QR here)")
        click.echo(f"\n   {url}\n")
        click.echo("   When the phone asks, allow 'install from unknown sources'.")
        click.echo("   Press Ctrl+C to stop the server — the .apk stays on disk.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            click.echo("\nStopped.")
        finally:
            httpd.server_close()
    elif not usb:
        click.echo("\nTo get it onto a phone, copy the .apk over — or re-run with:")
        click.echo("   apkpy run --qr     (scan a QR to install over Wi-Fi)")
        click.echo("   apkpy run --usb    (install through a USB cable)")


@main.command()
@click.option('--aab', is_flag=True, help="Build an .aab (App Bundle for the Play Store) instead of a signed .apk.")
@click.option('--name', default=None, help="App name (overrides apkpy.toml for this build).")
def release(aab, name):
    """Build a SIGNED release — ready for the Play Store (.aab) or a trusted install (.apk)."""
    python_code = _read_writehere()
    if python_code is None:
        return

    config = _load_or_prompt_config(name)
    if name:
        config["name"] = name
    app_name = _sanitize_name(name or config["name"])

    # 1) Toolchain (also gives us the JDK that owns keytool).
    tc = nb.discover_toolchain()
    if not (tc['jdk_home'] and tc['sdk'] and tc['gradle']):
        _toolchain_help(tc)
        return
    click.echo(f"Toolchain OK — JDK {tc['jdk_major']}, Android SDK, Gradle {nb.GRADLE_VERSION}.")

    # 2) Signing key — created once per application_id and reused for every update.
    signing = nb.ensure_keystore(tc['jdk_home'], config['application_id'], config['name'],
                                 log=click.echo)
    if not signing:
        click.echo("Could not prepare the signing key — see the error above.")
        return

    # 3) Generate the project (signed) and compile the release artifact.
    build_dir = os.path.join(nb.apkpy_home(), "build", app_name)
    os.makedirs(os.path.dirname(build_dir), exist_ok=True)
    _generate_android_project(python_code, build_dir, app_name, config=config, signing=signing)
    nb.write_local_properties(build_dir, tc['sdk'])

    kind = "App Bundle (.aab)" if aab else "APK"
    task = "bundleRelease" if aab else "assembleRelease"
    click.echo(f"\nBuilding a SIGNED {kind} with Gradle (the first build is slower)...\n")
    gradle_output = []
    if not nb.gradle_assemble(build_dir, tc['jdk_home'], tc['sdk'], tc['gradle'],
                              task=task, capture=gradle_output):
        click.echo(render_diagnostic(diagnose_build_failure(
            "\n".join(gradle_output), task=task, project_dir=build_dir,
        )))
        return

    artifact = nb.find_built_aab(build_dir) if aab else nb.find_built_apk(build_dir, release=True)
    if not artifact:
        click.echo("Build succeeded but no signed artifact was produced.")
        return

    ext = "aab" if aab else "apk"
    dest = os.path.abspath(f"{app_name}-release.{ext}")
    shutil.copyfile(artifact, dest)
    click.echo(f"\nSigned {ext.upper()} ready:  {dest}  ({os.path.getsize(dest) // 1024} KB)")
    click.echo(f"   App: {config['name']}  (id: {config['application_id']}, v{config['version_name']})")

    # 4) The keystore is precious — losing it means no more Play Store updates.
    click.echo(f"\n   Signing key: {signing['keystore']}")
    click.echo("   *** BACK UP this keystore file and keep it safe. ***")
    click.echo("   You need the SAME key to publish every future update of this app.")
    if aab:
        click.echo("\n   Upload the .aab in the Google Play Console:")
        click.echo("   https://play.google.com/console")
    else:
        click.echo("\n   This signed .apk installs directly on any phone (no 'unsigned' warning).")


@main.command()
def doctor():
    """Check whether this machine can build APKs with 'apkpy run'."""
    tc = nb.discover_toolchain()
    click.echo("\napkpy doctor — Android build toolchain\n")
    click.echo(f"   JDK (17-21) : {tc['jdk_home']}  [v{tc['jdk_major']}]"
               if tc['jdk_home'] else "   JDK (17-21) : NOT FOUND")
    click.echo(f"   Android SDK : {tc['sdk']}" if tc['sdk'] else "   Android SDK : NOT FOUND")
    if tc['sdk']:
        # The level apps are built for. Not a reason to say NOT READY: the
        # build downloads a platform that is missing, when it can.
        click.echo(f"   API {appconfig.COMPILE_SDK}      : " + (
            "installed" if nb.has_platform(tc['sdk'])
            else "not installed yet -- the first build downloads it, or run 'apkpy setup'"))
    click.echo(
        f"   Gradle {nb.GRADLE_VERSION}  : {tc['gradle']}"
        if tc['gradle']
        else f"   Gradle {nb.GRADLE_VERSION}  : NOT FOUND"
    )
    if tc['system_java'] and (not tc['jdk_home'] or tc['system_java'] > nb.JDK_MAX):
        click.echo(
            f"\n   note: 'java' on PATH is v{tc['system_java']} "
            f"(Gradle {nb.GRADLE_VERSION} needs 17-21)."
        )

    ready = all((tc['jdk_home'], tc['sdk'], tc['gradle']))
    click.echo("\n   => " + ("READY — run 'apkpy run' to build an APK."
                             if ready else "NOT READY — run 'apkpy setup' to install what's missing."))


@main.command()
def setup():
    """Download a compatible JDK / Gradle / Android SDK into ~/.apkpy."""
    tc = nb.discover_toolchain()

    if tc['jdk_home']:
        click.echo(f"JDK OK (v{tc['jdk_major']}).")
        jdk = tc['jdk_home']
    else:
        click.echo("Installing JDK 17...")
        jdk = nb.bootstrap_jdk(log=click.echo)
        click.echo("   JDK installed." if jdk else "   JDK install FAILED.")

    if tc['gradle']:
        click.echo("Gradle OK.")
    else:
        click.echo(f"Installing Gradle {nb.GRADLE_VERSION}...")
        g = nb.bootstrap_gradle(log=click.echo)
        click.echo("   Gradle installed." if g else "   Gradle install FAILED.")

    if tc['sdk']:
        # An SDK that is there is not always the SDK the builds need: they
        # moved to API 36, and "Android SDK OK" was said to one that had 35.
        if nb.has_platform(tc['sdk']):
            click.echo("Android SDK OK.")
        elif jdk and nb.install_platform(tc['sdk'], jdk, log=click.echo):
            click.echo(f"Android SDK OK (API {appconfig.COMPILE_SDK} platform added).")
        else:
            click.echo(
                f"Android SDK found, without the API {appconfig.COMPILE_SDK} platform. "
                "The first build downloads it; or tick it in Android Studio's SDK Manager.")
    elif jdk:
        click.echo("Installing the Android SDK (this is the big one)...")
        s = nb.bootstrap_sdk(jdk, log=click.echo)
        click.echo("   SDK installed." if s
                   else "   SDK install FAILED — install Android Studio or set ANDROID_HOME.")
    else:
        click.echo("Skipping SDK (needs a working JDK first).")

    click.echo("\nDone. Check with:  apkpy doctor")
