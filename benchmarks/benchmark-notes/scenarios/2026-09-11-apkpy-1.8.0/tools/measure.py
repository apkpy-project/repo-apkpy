# -*- coding: utf-8 -*-
"""Benchmark Notes, 2026-09-11 scenario: device measurements and a working-app check.

The cold-start and memory reading is the one recorded on 2026-08-17:

  force-stop, 250 ms, `am start -W`, the first TotalTime/WaitTime value, then two
  seconds and TOTAL PSS from `dumpsys meminfo`.

Three things are added, each because this run needed it.

1. A functional check. The earlier "UI smoke" only confirmed that four labels
   existed, which an app can pass while its list is empty and its search does
   nothing -- and ApkPy's did. Every app now has to show 100 notes, filter to 20
   favourites, add a note, and find one match for a search, read back from the
   screen after each action.

2. A warm-up to a steady state. A 2 GB emulator with Play services keeps
   settling for minutes after it boots and after an install: the same APK timed
   5.7 s, 4.1 s and 1.4 s depending only on when the launch happened. Before any
   launch is timed, the app is cold-started until three launches in a row agree
   within 15 %.

3. Ten timed launches instead of three. The median of the first three is kept,
   so the figure can be set beside the published method; the median, minimum and
   maximum of all ten are reported so the spread is visible.

Usage:
  py measure.py --out results.json --app "ApkPy=path/to.apk" [--app "Flet=..."]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

# adb from the ADB variable, else from PATH. The copy that ran named the SDK
# folder of the machine it ran on; that is the only difference.
ADB = os.environ.get('ADB') or shutil.which('adb') or 'adb'
SERIAL = os.environ.get('ANDROID_SERIAL', 'emulator-5554')
DUMP = '/sdcard/bench-ui.xml'

TARGETS = {
    'ApkPy': ('com.apkpy.benchmark.apkpy', 'com.apkpy.app.Screen_homeActivity'),
    'Flet': ('com.apkpy.benchmark.benchmark_notes_flet',
             'com.apkpy.benchmark.benchmark_notes_flet.MainActivity'),
    'BeeWare/Toga': ('com.apkpy.benchmark.benchmark_notes',
                     'org.beeware.android.MainActivity'),
}
LABELS = ('Benchmark Notes', 'Search notes', 'FAVORITES ONLY', 'ADD NOTE')

WARM_TOLERANCE = 0.15
WARM_WINDOW = 3
WARM_LIMIT = 12
TIMED_RUNS = 10


def adb(*args, timeout=120):
    done = subprocess.run([ADB, '-s', SERIAL] + list(args), capture_output=True,
                          timeout=timeout)
    return (done.stdout + done.stderr).decode('utf-8', 'replace')


def device():
    props = {}
    for key in ('ro.product.model', 'ro.build.version.sdk', 'ro.product.cpu.abi',
                'ro.build.fingerprint'):
        props[key] = adb('shell', 'getprop', key).strip()
    props['page_size'] = adb('shell', 'getconf', 'PAGESIZE').strip()
    return props


def screen(attempts=3):
    """Every visible node as (text, bounds); [] only when the screen truly
    could not be read.

    Text and content-desc both count, because Flutter exposes its widgets
    through semantics rather than TextViews. uiautomator refuses to dump while
    the UI is still busy -- just after a reboot it produced nothing, and the
    first pass read an empty screen and failed an app that was working. The old
    dump is deleted first, so a stale file from another app is never read.
    """
    for _ in range(attempts):
        adb('shell', 'rm', '-f', DUMP)
        said = adb('shell', 'uiautomator', 'dump', DUMP, timeout=60)
        if 'dumped to' in said:
            raw = adb('shell', 'cat', DUMP)
            start = raw.find('<?xml')
            if start >= 0:
                try:
                    root = ET.fromstring(raw[start:])
                except ET.ParseError:
                    root = None
                if root is not None:
                    nodes = []
                    for node in root.iter('node'):
                        for attr in ('text', 'content-desc', 'hint'):
                            value = (node.get(attr) or '').strip()
                            if value:
                                nodes.append((value, node.get('bounds', '')))
                    if nodes:
                        return nodes
        time.sleep(1.0)
    return []


def status(nodes):
    for text, _ in nodes:
        for line in text.splitlines():
            m = re.fullmatch(r'Showing (\d+) notes', line.strip())
            if m:
                return int(m.group(1))
    return None


def wait_for_status(expected, seconds=20):
    deadline = time.time() + seconds
    seen, nodes = None, []
    while time.time() < deadline:
        nodes = screen()
        seen = status(nodes)
        if seen == expected:
            return True, seen, nodes
        time.sleep(0.7)
    return False, seen, nodes


def centre(bounds):
    m = re.findall(r'\[(\d+),(\d+)\]', bounds or '')
    if len(m) != 2:
        return None
    (x1, y1), (x2, y2) = [(int(a), int(b)) for a, b in m]
    return (x1 + x2) // 2, (y1 + y2) // 2


def tap_label(nodes, label):
    for text, bounds in nodes:
        if label.lower() in text.lower():
            point = centre(bounds)
            if point:
                adb('shell', 'input', 'tap', str(point[0]), str(point[1]))
                return True
    return False


def stop_all():
    """Force-stop every benchmark app, not only the one about to be measured.

    A stack measured earlier stays alive holding hundreds of megabytes, and on a
    2 GB emulator that pushes the next app into swap.
    """
    for package, _ in TARGETS.values():
        adb('shell', 'am', 'force-stop', package)


def functional_once(package, activity):
    stop_all()
    time.sleep(0.5)
    adb('shell', 'am', 'start', '-n', '%s/%s' % (package, activity))
    steps = []

    ok, seen, nodes = wait_for_status(100, seconds=40)
    labels = {label: any(label.lower() in t.lower() for t, _ in nodes) for label in LABELS}
    first_note = any(re.fullmatch(r'Note 001', t.strip()) for t, _ in nodes)
    unreadable = not nodes
    steps.append({'step': 'opens with 100 notes', 'expected': 100, 'seen': seen,
                  'pass': ok and first_note, 'note_001_visible': first_note})
    if unreadable:
        return {'labels': labels, 'labels_found': 0, 'steps': steps,
                'passed': False, 'screen_unreadable': True}

    for label, expected, name in (('FAVORITES ONLY', 20, 'favourites filter'),
                                  ('FAVORITES ONLY', 100, 'favourites off again'),
                                  ('ADD NOTE', 101, 'add a note')):
        tapped = tap_label(screen(), label)
        ok, seen, _ = wait_for_status(expected) if tapped else (False, None, [])
        steps.append({'step': name, 'expected': expected, 'seen': seen,
                      'pass': bool(tapped and ok)})

    tapped = tap_label(screen(), 'Search notes')
    if tapped:
        time.sleep(0.8)
        adb('shell', 'input', 'text', 'Note%s010')
    ok, seen, _ = wait_for_status(1) if tapped else (False, None, [])
    steps.append({'step': 'search "Note 010"', 'expected': 1, 'seen': seen,
                  'pass': bool(tapped and ok)})

    return {'labels': labels, 'labels_found': sum(labels.values()), 'steps': steps,
            'passed': all(s['pass'] for s in steps), 'screen_unreadable': False}


def functional_check(package, activity, attempts=2):
    """Drive the four behaviours. An unreadable screen is an instrument failure,
    not an app failure, so it is retried and recorded rather than reported as
    the app not working."""
    tries = []
    for _ in range(attempts):
        result = functional_once(package, activity)
        tries.append(result)
        if not result['screen_unreadable']:
            break
        time.sleep(3)
    final = dict(tries[-1])
    final['attempts'] = len(tries)
    final['unreadable_attempts'] = sum(1 for t in tries if t['screen_unreadable'])
    return final


def one_cold_start(package, activity, read_memory=True):
    adb('shell', 'am', 'force-stop', package)
    time.sleep(0.25)
    out = adb('shell', 'am', 'start', '-W', '-n', '%s/%s' % (package, activity))
    first = re.search(r'(?m)(?:WaitTime|TotalTime):\s*(\d+)', out)
    total = re.search(r'(?m)^TotalTime:\s*(\d+)', out)
    wait = re.search(r'(?m)^WaitTime:\s*(\d+)', out)
    state = re.search(r'(?m)^LaunchState:\s*(\w+)', out)
    sample = {
        'cold_start_ms': int(first.group(1)) if first else None,
        'total_time_ms': int(total.group(1)) if total else None,
        'wait_time_ms': int(wait.group(1)) if wait else None,
        'launch_state': state.group(1) if state else None,
    }
    if read_memory:
        time.sleep(2)
        memory = adb('shell', 'dumpsys', 'meminfo', package)
        pss = re.search(r'TOTAL PSS:\s*(\d+)', memory)
        sample['pss_kb'] = int(pss.group(1)) if pss else None
    return sample


def warm_up(package, activity):
    """Cold-start until WARM_WINDOW launches in a row agree within WARM_TOLERANCE."""
    samples = []
    for _ in range(WARM_LIMIT):
        s = one_cold_start(package, activity, read_memory=False)
        samples.append(s['cold_start_ms'])
        recent = [v for v in samples[-WARM_WINDOW:] if v]
        if len(recent) == WARM_WINDOW and \
                (max(recent) - min(recent)) <= WARM_TOLERANCE * statistics.median(recent):
            return samples, True
        time.sleep(1)
    return samples, False


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest().upper()


def summary(values):
    values = [v for v in values if v is not None]
    if not values:
        return {'median': None, 'min': None, 'max': None}
    return {'median': statistics.median(values), 'min': min(values), 'max': max(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--app', action='append', required=True,
                        help='Framework=path/to/app.apk')
    args = parser.parse_args()

    result = {'date': time.strftime('%Y-%m-%d'), 'device': device(),
              'method': {'warm_tolerance': WARM_TOLERANCE, 'warm_window': WARM_WINDOW,
                         'warm_limit': WARM_LIMIT, 'timed_runs': TIMED_RUNS},
              'apps': []}
    for spec in args.app:
        framework, apk = spec.split('=', 1)
        package, activity = TARGETS[framework]
        print('== %s' % framework, flush=True)
        stop_all()
        adb('uninstall', package, timeout=120)
        install = adb('install', '-r', apk, timeout=600).strip().splitlines()
        entry = {
            'framework': framework, 'package': package, 'activity': activity,
            'apk_bytes': os.path.getsize(apk),
            'apk_mib': round(os.path.getsize(apk) / 1048576, 2),
            'sha256': sha256(apk), 'install': install[-1] if install else '',
        }
        entry['functional'] = functional_check(package, activity)
        print('   functional passed: %s (unreadable attempts: %d)' % (
            entry['functional']['passed'], entry['functional']['unreadable_attempts']),
              flush=True)

        warm, settled = warm_up(package, activity)
        entry['warm_up'] = {'samples_ms': warm, 'settled': settled}
        print('   warm-up %s: %s' % ('settled' if settled else 'DID NOT SETTLE', warm),
              flush=True)

        runs = [dict(one_cold_start(package, activity), run=i + 1)
                for i in range(TIMED_RUNS)]
        entry['runs'] = runs
        first3 = runs[:3]
        entry['published_method'] = {
            'cold_start_median_ms': summary([r['cold_start_ms'] for r in first3])['median'],
            'pss_median_kb': summary([r['pss_kb'] for r in first3])['median'],
        }
        entry['all_runs'] = {
            'cold_start_ms': summary([r['cold_start_ms'] for r in runs]),
            'pss_kb': summary([r['pss_kb'] for r in runs]),
            'launch_states': sorted({r['launch_state'] for r in runs if r['launch_state']}),
        }
        print('   first 3 (published method): %s ms, PSS %s kB' % (
            entry['published_method']['cold_start_median_ms'],
            entry['published_method']['pss_median_kb']), flush=True)
        print('   all %d: median %s ms (min %s, max %s)' % (
            TIMED_RUNS, entry['all_runs']['cold_start_ms']['median'],
            entry['all_runs']['cold_start_ms']['min'],
            entry['all_runs']['cold_start_ms']['max']), flush=True)
        result['apps'].append(entry)
        adb('shell', 'am', 'force-stop', package)

    with open(args.out, 'w', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    print('guardado em', args.out)


if __name__ == '__main__':
    sys.exit(main())
