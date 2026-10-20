"""
Native APK build pipeline for ``apkpy run``.

This module orchestrates the Android toolchain around the project that
``apkpy build`` already knows how to generate. It does three things:

1. **Discover** a usable toolchain — a JDK that Gradle 8.7 can run on
   (Java 17–21), the Android SDK, and a Gradle launcher.
2. **Compile** the generated Gradle project into a real ``app-debug.apk``.
3. **Deliver** it — the APK is always copied next to the user's script; a phone
   can optionally pull it over the LAN via an HTTP server + QR code, or by USB
   with ``adb``.

Nothing here touches the transpiler. The QR step is *optional*: the ``.apk``
file is written to the user's folder regardless, so anyone who doesn't want to
scan a QR can just grab the file and install it however they like.
"""
import collections
import os
import re
import sys
import glob
import shutil
import socket
import platform
import json
import hashlib
import zipfile
import tarfile
import urllib.parse
import urllib.request
import subprocess
import http.server
import socketserver

from .config import COMPILE_SDK

IS_WIN = os.name == "nt"

# Gradle 8.7 + AGP 8.6.1 (what generate_gradle_files() pins) run on JDK 17..21.
# Newer JDKs are deliberately excluded from the managed build pipeline.
GRADLE_VERSION = "8.7"
JDK_MIN, JDK_MAX = 17, 21


# ──────────────────────────────────────────────────────────────────────────
#  Paths / small helpers
# ──────────────────────────────────────────────────────────────────────────
def apkpy_home():
    return os.path.join(os.path.expanduser("~"), ".apkpy")


def _exe(name):
    return name + (".exe" if IS_WIN else "")


def _normalize_jdk_home(path):
    """Return the directory that actually contains bin/java, or None.

    Accepts either a JDK home directly, or a parent that holds a single
    extracted ``jdk-xx`` folder (how ``apkpy setup`` lays it down).
    """
    if not path:
        return None
    if os.path.isfile(os.path.join(path, "bin", _exe("java"))):
        return path
    for hit in glob.glob(os.path.join(path, "*", "bin", _exe("java"))):
        return os.path.dirname(os.path.dirname(hit))
    return None


# ──────────────────────────────────────────────────────────────────────────
#  Toolchain discovery
# ──────────────────────────────────────────────────────────────────────────
def java_major(java_home):
    """Major version int of the JDK at *java_home*, or None if it can't run."""
    java = os.path.join(java_home, "bin", _exe("java"))
    if not os.path.isfile(java):
        return None
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True)
    except Exception:
        return None
    text = (out.stderr or "") + (out.stdout or "")
    m = re.search(r'version "(\d+)(?:\.(\d+))?', text)
    if not m:
        return None
    major = int(m.group(1))
    if major == 1 and m.group(2):  # legacy "1.8.0" → 8
        major = int(m.group(2))
    return major


def _android_studio_jbr_candidates():
    out = []
    if IS_WIN:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                out.append(os.path.join(base, "Android", "Android Studio", "jbr"))
                out.append(os.path.join(base, "Programs", "Android Studio", "jbr"))
    elif sys.platform == "darwin":
        out.append("/Applications/Android Studio.app/Contents/jbr/Contents/Home")
        out.append(os.path.expanduser(
            "~/Applications/Android Studio.app/Contents/jbr/Contents/Home"))
    else:
        out.append("/opt/android-studio/jbr")
        out.append(os.path.expanduser("~/android-studio/jbr"))
    return out


def find_jdk():
    """Return ``(java_home, major)`` for a JDK Gradle can run on, else ``(None, None)``.

    Search order: apkpy-managed JDK → Android Studio's bundled runtime →
    ``JAVA_HOME`` → ``java`` on PATH. A JDK is only accepted if its major
    version is in the ``JDK_MIN..JDK_MAX`` window.
    """
    candidates = [os.path.join(apkpy_home(), "jdk")]
    candidates += _android_studio_jbr_candidates()
    if os.environ.get("JAVA_HOME"):
        candidates.append(os.environ["JAVA_HOME"])
    on_path = shutil.which("java")
    if on_path:
        candidates.append(os.path.dirname(os.path.dirname(on_path)))

    seen = set()
    for raw in candidates:
        home = _normalize_jdk_home(raw)
        if not home or home in seen:
            continue
        seen.add(home)
        major = java_major(home)
        if major and JDK_MIN <= major <= JDK_MAX:
            return home, major
    return None, None


def find_android_sdk():
    """Locate the Android SDK, or None. Prefers apkpy-managed, then env, then OS default."""
    candidates = [
        os.path.join(apkpy_home(), "sdk"),
        os.environ.get("ANDROID_SDK_ROOT", ""),
        os.environ.get("ANDROID_HOME", ""),
    ]
    if IS_WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        if la:
            candidates.append(os.path.join(la, "Android", "Sdk"))
    elif sys.platform == "darwin":
        candidates.append(os.path.expanduser("~/Library/Android/sdk"))
    else:
        candidates.append(os.path.expanduser("~/Android/Sdk"))

    # A real SDK has either installed platforms or platform-tools.
    for sdk in candidates:
        if sdk and (os.path.isdir(os.path.join(sdk, "platforms"))
                    or os.path.isdir(os.path.join(sdk, "platform-tools"))):
            return sdk
    return None


def find_gradle():
    """Locate the pinned Gradle launcher, or None.

    Order: apkpy-managed → the wrapper distribution Gradle already cached under
    ``~/.gradle/wrapper/dists`` → ``gradle`` on PATH.
    """
    launcher = "gradle.bat" if IS_WIN else "gradle"

    managed = os.path.join(apkpy_home(), "gradle", f"gradle-{GRADLE_VERSION}", "bin", launcher)
    if os.path.isfile(managed):
        return managed

    pattern = os.path.join(
        os.path.expanduser("~"), ".gradle", "wrapper", "dists",
        f"gradle-{GRADLE_VERSION}-bin", "*", f"gradle-{GRADLE_VERSION}", "bin", launcher,
    )
    hits = glob.glob(pattern)
    if hits:
        return hits[0]

    on_path = shutil.which("gradle")
    if on_path:
        return on_path
    return None


def system_java_major():
    """Major version of whatever ``java`` is on PATH, or None.

    Used only to warn when the only Java around is too new for managed Gradle
    (this machine ships Java 26), so the message can point at ``apkpy setup``.
    """
    on_path = shutil.which("java")
    if not on_path:
        return None
    home = _normalize_jdk_home(os.path.dirname(os.path.dirname(on_path)))
    return java_major(home) if home else None


def discover_toolchain():
    """Return a dict describing what was found (values may be None)."""
    jdk_home, jdk_major = find_jdk()
    return {
        "jdk_home": jdk_home,
        "jdk_major": jdk_major,
        "sdk": find_android_sdk(),
        "gradle": find_gradle(),
        "system_java": system_java_major(),
    }


# ──────────────────────────────────────────────────────────────────────────
#  Build
# ──────────────────────────────────────────────────────────────────────────
def write_local_properties(project_dir, sdk_path):
    """Point Gradle at the SDK (forward slashes are valid on every OS here)."""
    with open(os.path.join(project_dir, "local.properties"), "w", encoding="utf-8") as f:
        f.write("sdk.dir=" + sdk_path.replace("\\", "/") + "\n")


# Gradle output is streamed live *and* kept, so a failure can be explained
# instead of leaving the reader to scroll back through it.  Only the tail is
# retained: a successful first build prints thousands of progress lines.
_GRADLE_TAIL_LINES = 400


def gradle_assemble(project_dir, jdk_home, sdk_path, gradle_launcher, release=False,
                    task=None, capture=None):
    """Run a Gradle task (default ``assembleDebug``/``assembleRelease``), streaming
    output. Pass ``task`` to override (e.g. ``bundleRelease`` for an .aab).
    Returns bool ok.

    ``capture`` may be a list; the tail of Gradle's combined output is appended
    to it so the caller can diagnose a failure.
    """
    if task is None:
        task = "assembleRelease" if release else "assembleDebug"
    args = [task, "--no-daemon", f"-Dorg.gradle.java.home={jdk_home}"]
    if IS_WIN:
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", gradle_launcher] + args
    else:
        cmd = [gradle_launcher] + args

    env = dict(os.environ)
    env["JAVA_HOME"] = jdk_home
    env["ANDROID_SDK_ROOT"] = sdk_path
    env["ANDROID_HOME"] = sdk_path

    if capture is None:
        proc = subprocess.run(cmd, cwd=project_dir, env=env)
        return proc.returncode == 0

    tail = collections.deque(maxlen=_GRADLE_TAIL_LINES)
    proc = subprocess.Popen(
        cmd, cwd=project_dir, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            tail.append(line.rstrip())
    finally:
        proc.stdout.close()
        proc.wait()
    capture.extend(tail)
    return proc.returncode == 0


def find_built_apk(project_dir, release=False):
    sub = "release" if release else "debug"
    out_dir = os.path.join(project_dir, "app", "build", "outputs", "apk", sub)
    if not os.path.isdir(out_dir):
        return None
    # Prefer the canonical name, else any .apk in the output dir.
    canonical = os.path.join(out_dir, f"app-{sub}.apk")
    if os.path.isfile(canonical):
        return canonical
    apks = sorted(glob.glob(os.path.join(out_dir, "*.apk")))
    return apks[0] if apks else None


def find_built_aab(project_dir):
    """Path to the built release App Bundle (.aab), or None."""
    out_dir = os.path.join(project_dir, "app", "build", "outputs", "bundle", "release")
    if not os.path.isdir(out_dir):
        return None
    canonical = os.path.join(out_dir, "app-release.aab")
    if os.path.isfile(canonical):
        return canonical
    aabs = sorted(glob.glob(os.path.join(out_dir, "*.aab")))
    return aabs[0] if aabs else None


# ──────────────────────────────────────────────────────────────────────────
#  Signing (release keystore) — needed for the Play Store / a trusted install
# ──────────────────────────────────────────────────────────────────────────
def keystores_dir():
    d = os.path.join(apkpy_home(), "keystores")
    os.makedirs(d, exist_ok=True)
    return d


def ensure_keystore(jdk_home, application_id, app_name, log=print):
    """Return the signing info for `application_id`, creating the keystore (via
    `keytool`) the first time. Stored under ~/.apkpy/keystores so the SAME key is
    reused for every release of this app — the Play Store requires that for
    updates. Returns a dict {keystore, store_password, key_password, key_alias},
    or None on failure."""
    import json
    import secrets

    safe = re.sub(r'[^a-zA-Z0-9._-]+', '_', application_id or "app") or "app"
    ks_path = os.path.join(keystores_dir(), safe + ".jks")
    meta_path = os.path.join(keystores_dir(), safe + ".json")

    # Reuse an existing keystore (so app updates keep the same signing identity).
    if os.path.isfile(ks_path) and os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            meta["keystore"] = ks_path
            return meta
        except Exception:
            pass  # corrupt metadata — fall through and recreate

    password = secrets.token_urlsafe(18)
    alias = "apkpy"
    dname = "CN=" + (app_name or "ApkPy App").replace(",", " ").strip() + ", O=ApkPy, C=US"
    keytool = os.path.join(jdk_home, "bin", _exe("keytool"))
    cmd = [
        keytool, "-genkeypair", "-v",
        "-keystore", ks_path, "-alias", alias,
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", password, "-keypass", password,
        "-dname", dname,
    ]
    env = dict(os.environ)
    env["JAVA_HOME"] = jdk_home
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    except Exception as e:
        log(f"Could not run keytool ({e}).")
        return None
    if proc.returncode != 0 or not os.path.isfile(ks_path):
        log("keytool failed to create the keystore:\n" + (proc.stderr or proc.stdout or ""))
        return None

    meta = {"store_password": password, "key_password": password, "key_alias": alias}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    meta["keystore"] = ks_path
    log(f"Created a release signing key at {ks_path}")
    return meta


# ──────────────────────────────────────────────────────────────────────────
#  Delivery (all optional — the .apk file is always written to disk first)
# ──────────────────────────────────────────────────────────────────────────
def lan_ip():
    """Best-effort LAN IP this machine is reachable at, for the phone to hit."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def print_qr(url):
    """Print a scannable ASCII QR for *url*. Returns False if qrcode isn't installed."""
    try:
        import qrcode
    except ImportError:
        return False
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    # Two cells wide per module keeps the QR roughly square in a terminal.
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")  # cp1252 consoles can't do █
        dark, light = "██", "  "
        for row in matrix:
            print("".join(dark if cell else light for cell in row))
    except Exception:
        for row in matrix:
            print("".join("##" if cell else "  " for cell in row))
    return True


def make_apk_server(apk_path, port=8000, tries=20, host="0.0.0.0"):
    """Serve *apk_path*, and nothing else, over HTTP. Returns ``(httpd, url)``.

    The phone has to reach it, so the server listens on every interface; what
    it answers is the one file. It used to serve the APK's whole folder --
    usually the project, with a listing -- to anyone on the network while the
    QR was up. Every other path is a 404."""
    directory = os.path.dirname(os.path.abspath(apk_path))
    filename = os.path.basename(apk_path)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=directory, **k)

        def send_head(self):
            # GET and HEAD both come through here, before any file is opened.
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            if path != "/" + filename:
                self.send_error(404)
                return None
            return super().send_head()

        def log_message(self, *a):
            pass  # keep the console clean

    Handler.extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map)
    Handler.extensions_map[".apk"] = "application/vnd.android.package-archive"

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    last_err = None
    for p in range(port, port + tries):
        try:
            httpd = Server((host, p), Handler)
            return httpd, f"http://{lan_ip()}:{p}/{urllib.parse.quote(filename)}"
        except OSError as e:
            last_err = e
    raise last_err


def adb_devices(sdk_path):
    adb = os.path.join(sdk_path, "platform-tools", _exe("adb"))
    if not os.path.isfile(adb):
        return None
    try:
        out = subprocess.run([adb, "devices"], capture_output=True, text=True)
    except Exception:
        return None
    lines = [l for l in out.stdout.splitlines()[1:] if l.strip() and "\tdevice" in l]
    return [l.split("\t")[0] for l in lines]


def adb_install(sdk_path, apk_path):
    adb = os.path.join(sdk_path, "platform-tools", _exe("adb"))
    if not os.path.isfile(adb):
        return False, "adb not found in platform-tools"
    proc = subprocess.run([adb, "install", "-r", apk_path], capture_output=True, text=True)
    blob = (proc.stdout or "") + (proc.stderr or "")
    return (proc.returncode == 0 and "Success" in blob), blob.strip()


# ──────────────────────────────────────────────────────────────────────────
#  Bootstrap (`apkpy setup`) — auto-download a toolchain for machines that
#  don't already have Android Studio. JDK and Gradle install from stable URLs;
#  the SDK uses Google's command-line tools + sdkmanager.
# ──────────────────────────────────────────────────────────────────────────
# Google publishes no "latest" alias for the command-line tools, so the build
# number is pinned here and may need bumping over time. The sha1 and the size
# are the ones Google's own package list (repository2-3.xml) gives for these
# archives -- what sdkmanager checks its own downloads against. Bumping the
# build means copying the new three from that list.
_CMDLINE_TOOLS = {
    "win":   ("https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip",
              "3d2917302740f476999a091bc5558837c7a863c5", 153583359),
    "mac":   ("https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip",
              "37fb7dd41005b3b4ca6ea48ac27074b6fc4e3236", 153607488),
    "linux": ("https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip",
              "d313adb7aedccf6cf0cfca51ec180f0059f5f8f8", 153607504),
}
_SDK_PACKAGES = ["platform-tools", "platforms;android-%d" % COMPILE_SDK, "build-tools;34.0.0"]


def has_platform(sdk_path, level=COMPILE_SDK):
    """Whether the SDK holds the Android platform the builds are made against."""
    return bool(sdk_path) and os.path.isfile(
        os.path.join(sdk_path, "platforms", "android-%d" % level, "android.jar"))


def install_platform(sdk_path, jdk_home, level=COMPILE_SDK, log=print):
    """Add the platform to an SDK that is already there, with its own
    sdkmanager. True when the platform is installed afterwards.

    `apkpy setup` used to stop at "Android SDK OK" for any SDK it found, so
    the level the builds moved to was never installed by it. An SDK that came
    with Android Studio may have no command-line tools: then there is nothing
    to run here, and the caller says where the box to tick is.
    """
    if has_platform(sdk_path, level):
        return True
    name = "sdkmanager.bat" if IS_WIN else "sdkmanager"
    found = sorted(glob.glob(os.path.join(sdk_path or "", "cmdline-tools", "*", "bin", name)))
    if not found or not jdk_home:
        return False
    env = dict(os.environ)
    env["JAVA_HOME"] = jdk_home
    try:
        log("   installing the Android platform, API %d ..." % level)
        subprocess.run([found[-1], f"--sdk_root={sdk_path}", "platforms;android-%d" % level],
                       input="y\n" * 10, text=True, env=env)
    except Exception as e:
        log(f"   sdkmanager could not be run: {e}")
    return has_platform(sdk_path, level)


def _arch():
    m = platform.machine().lower()
    return "aarch64" if m in ("arm64", "aarch64") else "x64"


def _os_token():
    # Adoptium JDK API uses windows/mac/linux.
    if IS_WIN:
        return "windows"
    return "mac" if sys.platform == "darwin" else "linux"


def _fetch_text(url):
    """A small text file from *url*: a checksum or an API answer."""
    req = urllib.request.Request(url, headers={"User-Agent": "apkpy"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def _download(url, dest, log=print, sha256=None, sha1=None, size=None):
    """Download *url* into *dest* and check it against the checksum its
    publisher gives before anything is unpacked. A toolchain is code that
    runs on this machine: a file that does not match is deleted and the
    install stops. There is no unchecked download."""
    algorithm, wanted = ("sha256", sha256) if sha256 else ("sha1", sha1)
    if not wanted:
        raise ValueError(f"no checksum to check {url} against")
    name = urllib.parse.unquote(url.split("/")[-1].split("?")[0])
    log(f"   downloading {name} ...")
    digest = hashlib.new(algorithm)
    received = 0
    req = urllib.request.Request(url, headers={"User-Agent": "apkpy"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
            f.write(chunk)
            received += len(chunk)
    got = digest.hexdigest()
    if got != wanted.lower() or (size is not None and received != size):
        os.remove(dest)
        raise RuntimeError(
            f"{name} does not match the checksum its publisher gives "
            f"({algorithm} {got[:12]}..., expected {wanted.lower()[:12]}...), so it was deleted. "
            f"Run apkpy setup again; if it happens again, the download is being changed on the way.")
    log(f"   {algorithm} checked.")


def _inside(dest, name):
    """Where *name* lands under *dest*, or None when it lands outside it."""
    root = os.path.realpath(dest)
    target = os.path.realpath(os.path.join(root, name))
    return target if target == root or target.startswith(root + os.sep) else None


def _extract(archive, dest):
    """Unpack *archive* into *dest*. An entry that would land outside *dest*
    -- an absolute path, a ``..``, a link that points out -- stops the
    install before anything is written."""
    label = os.path.basename(archive)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if _inside(dest, name) is None:
                    raise RuntimeError(f"{label}: {name} would be written outside {dest}; not unpacked.")
            z.extractall(dest)
        return
    with tarfile.open(archive) as t:
        members = t.getmembers()
        for m in members:
            if _inside(dest, m.name) is None:
                raise RuntimeError(f"{label}: {m.name} would be written outside {dest}; not unpacked.")
            if m.issym() or m.islnk():
                # A hard link names a path in the archive; a symbolic link,
                # a path from the folder it sits in.
                target = m.linkname if m.islnk() else os.path.join(os.path.dirname(m.name), m.linkname)
                if os.path.isabs(m.linkname) or _inside(dest, target) is None:
                    raise RuntimeError(f"{label}: {m.name} links outside {dest}; not unpacked.")
            elif not (m.isfile() or m.isdir()):
                raise RuntimeError(f"{label}: {m.name} is a device or a pipe; not unpacked.")
        if hasattr(tarfile, "data_filter"):
            t.extractall(dest, members=members, filter="data")
        else:
            t.extractall(dest, members=members)


def _jdk_asset(listing):
    """(link, sha256, file name) of the JDK in Adoptium's answer."""
    for entry in listing:
        package = (entry.get("binary") or {}).get("package") or {}
        if package.get("link") and package.get("checksum"):
            return package["link"], package["checksum"], package.get("name") or ""
    raise RuntimeError("Adoptium listed no JDK 17 for this system.")


def bootstrap_jdk(log=print):
    """Install Temurin JDK 17 into ~/.apkpy/jdk. Returns the JDK home or None."""
    home = os.path.join(apkpy_home(), "jdk")
    existing = _normalize_jdk_home(home)
    if existing:
        return existing
    os.makedirs(home, exist_ok=True)
    # The assets query gives the download link with its sha256; the binary
    # redirect used before gave the file alone.
    query = (f"https://api.adoptium.net/v3/assets/latest/17/hotspot?os={_os_token()}"
             f"&architecture={_arch()}&image_type=jdk&vendor=eclipse")
    tmp = None
    try:
        link, sha256, name = _jdk_asset(json.loads(_fetch_text(query)))
        tmp = os.path.join(home, "jdk" + (".zip" if name.endswith(".zip") else ".tar.gz"))
        _download(link, tmp, log, sha256=sha256)
        _extract(tmp, home)
    except Exception as e:
        log(f"   JDK download failed: {e}")
        return None
    finally:
        if tmp and os.path.isfile(tmp):
            os.remove(tmp)
    return _normalize_jdk_home(home)


def bootstrap_gradle(log=print):
    """Install the pinned Gradle into ~/.apkpy/gradle."""
    base = os.path.join(apkpy_home(), "gradle")
    launcher = os.path.join(base, f"gradle-{GRADLE_VERSION}", "bin",
                            "gradle.bat" if IS_WIN else "gradle")
    if os.path.isfile(launcher):
        return launcher
    os.makedirs(base, exist_ok=True)
    url = f"https://services.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip"
    tmp = os.path.join(base, "gradle.zip")
    try:
        # Gradle publishes the sha256 beside every distribution.
        sha256 = _fetch_text(url + ".sha256").split()[0]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
            raise RuntimeError(f"no sha256 at {url}.sha256")
        _download(url, tmp, log, sha256=sha256)
        _extract(tmp, base)
    except Exception as e:
        log(f"   Gradle download failed: {e}")
        return None
    finally:
        if os.path.isfile(tmp):
            os.remove(tmp)
    return launcher if os.path.isfile(launcher) else None


def bootstrap_sdk(jdk_home, log=print):
    """Install the Android SDK bits into ~/.apkpy/sdk via Google's sdkmanager.

    Returns the SDK path or None. Raises nothing — logs and returns None on
    failure so the caller can fall back to guidance.
    """
    sdk = os.path.join(apkpy_home(), "sdk")
    try:
        os.makedirs(sdk, exist_ok=True)
        token = "win" if IS_WIN else ("mac" if sys.platform == "darwin" else "linux")
        # cmdline-tools must live at  <sdk>/cmdline-tools/latest/
        latest = os.path.join(sdk, "cmdline-tools", "latest")
        if not os.path.isfile(os.path.join(latest, "bin", _exe("sdkmanager")
                                           if not IS_WIN else "sdkmanager.bat")):
            staging = os.path.join(sdk, "_clt_tmp")
            if os.path.isdir(staging):
                shutil.rmtree(staging)
            tmp = os.path.join(sdk, "clt.zip")
            url, sha1, size = _CMDLINE_TOOLS[token]
            _download(url, tmp, log, sha1=sha1, size=size)
            _extract(tmp, staging)
            os.remove(tmp)
            os.makedirs(os.path.dirname(latest), exist_ok=True)
            if os.path.isdir(latest):
                shutil.rmtree(latest)
            shutil.move(os.path.join(staging, "cmdline-tools"), latest)
            shutil.rmtree(staging, ignore_errors=True)

        sdkmgr = os.path.join(latest, "bin", "sdkmanager.bat" if IS_WIN else "sdkmanager")
        env = dict(os.environ)
        env["JAVA_HOME"] = jdk_home
        # Accept licenses (feed "y" to every prompt), then install packages.
        log("   accepting SDK licenses ...")
        subprocess.run([sdkmgr, f"--sdk_root={sdk}", "--licenses"],
                       input="y\n" * 50, text=True, env=env)
        log("   installing platform-tools / android-%d / build-tools ..." % COMPILE_SDK)
        rc = subprocess.run([sdkmgr, f"--sdk_root={sdk}"] + _SDK_PACKAGES, env=env)
        if rc.returncode != 0:
            log("   sdkmanager returned a non-zero exit code.")
        return sdk if os.path.isdir(os.path.join(sdk, "platform-tools")) else None
    except Exception as e:
        log(f"   SDK bootstrap failed: {e}")
        return None
