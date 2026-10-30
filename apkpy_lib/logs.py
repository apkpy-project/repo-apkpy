"""apkpy logs: what the app on the phone prints, while it runs.

On the phone, print() in the app becomes android.util.Log.i("apkpy", ...), and
Android's own AndroidRuntime writes a crash. Both land in logcat, mixed with
the lines of every other app and of the system. This follows logcat through
adb and keeps what the app's own process writes:

- print() as it was printed;
- ApkPy's warnings and errors, with their level and tag, and the trace of
  an error the app's code caught (System.err);
- a crash, with its error and the app's own lines of the trace: the line of
  writehere.py each one came from, when the build left its map (load_lines).

What Android itself writes in the app's process is left out: phones log
errors there that are not the app's (a Xiaomi writes about ten at each
start). --all shows every line.

The process is found by the app's package (application_id in apkpy.toml):
from ActivityManager's "Start proc" line each time the app starts, and by
pidof every second and a half. Lines that came before their process was known
are kept for a while and shown once it is, so the first prints of an app
opened after the command are not lost. A crash and a reopen are followed too.
"""

import bisect
import collections
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time

# logcat -v threadtime:
# 10-29 18:43:01.123  1234  1250 I apkpy   : hello
LINE = re.compile(
    r'^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(?P<pid>\d+)\s+\d+\s+'
    r'(?P<level>[VDIWEFA])\s+(?P<tag>.*?)\s*:\s?(?P<msg>.*)$')
# ActivityManager: Start proc 12345:com.example.app/u0a234 for top-activity ...
STARTED = re.compile(r'\bStart proc (\d+):([A-Za-z][\w.]*)(?::[\w.]+)?/')
# ActivityManager: Process com.example.app (pid 12345) has died: fg  TOP
DIED = re.compile(r'\bProcess ([A-Za-z][\w.]*)(?::[\w.]+)? \(pid (\d+)\) has died')
# A frame of a trace that is Android's or Java's, not the app's.
_PLATFORM = re.compile(
    r'^\s*at (?:android|androidx|java|javax|jdk|kotlin|kotlinx|dalvik|libcore|sun|'
    r'com\.android|com\.google\.android|org\.json)\.')
_MORE = re.compile(r'^\s*\.\.\. \d+ more$')
# at com.example.Screen_homeActivity$3.onClick(Screen_homeActivity.java:812)
_FRAME = re.compile(r'^at (?P<where>[\w.$<>]+)\((?P<file>[\w$]+\.java):(?P<line>\d+)\)$')
# ApkPy's own tags: apkpy, ApkPy, ApkpyData, ApkpyContacts, ApkpyNfc...
_APP_TAG = re.compile(r'^apkpy', re.IGNORECASE)
_KEPT = 400                 # lines kept from processes not known yet


class Follower(object):
    """Turns logcat lines into what is shown, for one package.

    feed() takes a line as logcat writes it and answers the lines to show
    (often none). started() and stopped() keep the set of the app's
    processes, which is what decides whose lines are kept.
    """

    def __init__(self, package, everything=False, lines=None):
        self.package = package
        self.everything = everything
        self.lines = lines          # the build's map of Java lines, see load_lines()
        self.pids = set()
        self._in_crash = False
        self._last_place = None
        self._recent = collections.deque(maxlen=_KEPT)

    def started(self, pid):
        """The app has a process: what to say, then its lines seen so far."""
        if pid in self.pids:
            return []
        self.pids.add(pid)
        shown = ['-- %s started (pid %s) --' % (self.package, pid)]
        earlier = [parts for parts in self._recent if parts[0] == pid]
        self._recent = collections.deque(
            (parts for parts in self._recent if parts[0] != pid), maxlen=_KEPT)
        for parts in earlier:
            shown.extend(self._show(*parts))
        return shown

    def stopped(self, pid):
        if pid not in self.pids:
            return []
        self.pids.discard(pid)
        self._in_crash = False
        return ['-- %s stopped --' % self.package]

    def feed(self, line):
        found = LINE.match(line.rstrip('\r\n'))
        if not found:
            return []
        pid, level, tag, msg = found.group('pid', 'level', 'tag', 'msg')
        if tag == 'ActivityManager':
            start = STARTED.search(msg)
            if start and start.group(2) == self.package:
                return self.started(start.group(1))
            death = DIED.search(msg)
            if death and death.group(1) == self.package:
                return self.stopped(death.group(2))
        if pid not in self.pids:
            self._recent.append((pid, level, tag, msg))
            return []
        return self._show(pid, level, tag, msg)

    def _show(self, pid, level, tag, msg):
        if self.everything:
            return ['%s/%s: %s' % (level, tag, msg)]
        if tag == 'AndroidRuntime':
            return self._crash(msg)
        if tag == 'apkpy' and level == 'I':
            return [msg]
        if _APP_TAG.match(tag):
            return ['%s/%s: %s' % (level, tag, msg)]
        # A caught error's trace (e.printStackTrace() in the app's code).
        if tag == 'System.err' and not (_PLATFORM.match(msg) or _MORE.match(msg)):
            return ['%s/%s: %s' % (level, tag, msg)]
        # The rest is Android's own, in the app's process: phones log many
        # errors there that are not the app's (Zygote, HWUI, the maker's
        # services). --all shows them.
        return []

    def _crash(self, msg):
        if msg.startswith('FATAL EXCEPTION'):
            self._in_crash = True
            self._last_place = None
            return ['', 'The app stopped with an error:']
        if not self._in_crash or msg.startswith('Process: ') or _MORE.match(msg) \
                or _PLATFORM.match(msg):
            return []
        if msg.lstrip().startswith('at '):
            return self._frame(msg.strip())
        self._last_place = None
        return ['  ' + msg]

    def _frame(self, frame):
        """A line of the trace: the line of Python it came from when the
        build's map knows it, else the Java. With a map, ApkPy's own steps
        (ApkpyValues.toInt, a screen's _apkpy helpers) are left out: the
        line of Python that called them is the one to read."""
        found = _FRAME.match(frame)
        if not self.lines or not found:
            return ['    ' + frame]
        place = python_line(self.lines, found.group('file'), int(found.group('line')))
        if place:
            if place[:2] == self._last_place:
                return []
            self._last_place = place[:2]
            path, line, text = place
            return ['    at %s, line %d%s  (%s:%s)' % (
                path, line, ': ' + text if text else '',
                found.group('file'), found.group('line'))]
        method = found.group('where').rsplit('.', 1)[-1]
        if found.group('file').startswith('Apkpy') or method.startswith('_apkpy'):
            return []
        return ['    ' + frame]


def python_line(lines, java_file, java_line):
    """(file, line, text) of the Python a line of the generated Java came
    from, by the build's map; None for the Java's own lines."""
    runs = ((lines or {}).get('java') or {}).get(java_file)
    if not runs:
        return None
    at = bisect.bisect_right([run[0] for run in runs], java_line) - 1
    if at < 0 or not runs[at][1]:
        return None
    _start, line, path = runs[at]
    text = ((lines.get('text') or {}).get(path) or {}).get(str(line), '')
    return path, line, text


def load_lines(package):
    """The map `apkpy run` / `apkpy build` left for this app, or None.

    It is the last build of that application_id on this computer: an APK
    built elsewhere, or older than the last build, shows the wrong lines,
    which is why the Java line stays beside the Python one."""
    from .native_build import apkpy_home
    try:
        with open(os.path.join(apkpy_home(), 'lines', package + '.json'), encoding='utf-8') as f:
            found = json.load(f)
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) and found.get('version') == 1 else None


def find_adb(sdk=None):
    """adb from the Android SDK, else from the PATH; None if neither has it."""
    if sdk:
        path = os.path.join(sdk, 'platform-tools', 'adb.exe' if os.name == 'nt' else 'adb')
        if os.path.isfile(path):
            return path
    return shutil.which('adb')


def devices(adb):
    """[(serial, state)] as adb devices lists them: device, unauthorized..."""
    try:
        out = subprocess.run([adb, 'devices'], capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            found.append((parts[0], parts[1]))
    return found


def pids_of(adb, serial, package):
    """The pids the package runs as now, from pidof: an empty set if none,
    None if adb did not answer (which says nothing about the app)."""
    try:
        out = subprocess.run([adb, '-s', serial, 'shell', 'pidof', package],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return {p for p in out.split() if p.isdigit()}


def follow(adb, serial, package, everything=False, say=print, poll=1.5, lines=None):
    """Show the app's lines until Ctrl+C or until the phone goes away.

    Answers 0 after Ctrl+C, 1 if logcat stopped by itself."""
    follower = Follower(package, everything, lines)
    now = pids_of(adb, serial, package) or set()
    follower.pids.update(now)
    if now:
        say('Showing what %s prints on %s (pid %s). Ctrl+C to stop.'
            % (package, serial, ', '.join(sorted(now))))
    else:
        say('Waiting for %s on %s: open the app on the phone. Ctrl+C to stop.'
            % (package, serial))
    # -T 1: from now on, not the whole buffer of what came before.
    proc = subprocess.Popen([adb, '-s', serial, 'logcat', '-v', 'threadtime', '-T', '1'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = queue.Queue()

    def read():
        for raw in iter(proc.stdout.readline, b''):
            lines.put(raw.decode('utf-8', 'replace'))
        lines.put(None)

    threading.Thread(target=read, daemon=True).start()
    checked = time.time()
    try:
        while True:
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                line = ''
            if line is None:
                say('logcat stopped: is the phone still connected?')
                return 1
            for shown in follower.feed(line) if line else ():
                say(shown)
            if time.time() - checked >= poll:
                checked = time.time()
                now = pids_of(adb, serial, package)
                if now is None:
                    continue
                for pid in sorted(now - follower.pids):
                    for shown in follower.started(pid):
                        say(shown)
                for pid in sorted(follower.pids - now):
                    for shown in follower.stopped(pid):
                        say(shown)
    except KeyboardInterrupt:
        say('Stopped.')
        return 0
    finally:
        try:
            proc.terminate()
        except OSError:
            pass
