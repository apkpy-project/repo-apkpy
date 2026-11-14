"""The Publish and Help sections of the Studio. Publish only runs ApkPy's own commands, and shows what they say.

By Ruben Rego (the monster-rpg template's Studio), shared by every game's Studio."""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .ui import ACCENT, BAD, GOOD, MUTED, PANEL, Scrolling, px

# ApkPy's command line, as `apkpy run` runs it
START = "from apkpy_lib.cli import main; main()"
STATE_FILE = ".studio_release.json"
LOOK_AHEAD = "#b07010"
GUIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guide.md")      # what the Help section shows first
PLACEHOLDER_ID = re.compile(r"^(com\.apkpygame\.|com\.example\.|com\.test\.)")


def read_state(root):
    try:
        with open(os.path.join(root, STATE_FILE), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_state(root, **values):
    state = read_state(root)
    state.update(values)
    with open(os.path.join(root, STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def key_files(app_id):
    """The signing key of this game, where ApkPy keeps it: (the key, its passwords). The second is private too."""
    from .. import _host
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", app_id or "app") or "app"
    folder = _host.keystores_dir()
    return os.path.join(folder, safe + ".jks"), os.path.join(folder, safe + ".json")


def copy_key(app_id, folder):
    """A copy of the key and of its passwords. Gives back the two copies."""
    made = []
    for path in key_files(app_id):
        if not os.path.isfile(path):
            raise ValueError("This game has no signing key yet: it is made with the first signed version.")
        target = os.path.join(folder, os.path.basename(path))
        shutil.copy2(path, target)
        made.append(target)
    return made


def next_version(values):
    """The version after this one: the number goes up, and so does the last part of the name."""
    code = int(values.get("version_code") or 0) + 1
    parts = (values.get("version_name") or "0.1.0").split(".")
    if parts[-1].isdigit():
        parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts), str(code)


def checks(project, problems=(), icon_place="My game"):
    """What to look at before publishing: [(good: True, False or None for a remark, words)]. icon_place: the section
    where the icon is chosen."""
    app = project.app.values
    state = read_state(project.root)
    out = [(not problems, "No problems in the project." if not problems else "%d problem(s) at the bottom of the window: the build will stop." % len(problems))]
    out.append((not PLACEHOLDER_ID.match(app.get("application_id", "")), "App id: %s%s" % (app.get("application_id", ""), "" if not PLACEHOLDER_ID.match(app.get("application_id", "")) else ". Use your own in My game, before the first signed version: it cannot change after")))
    out.append((bool(app.get("icon")), "It has its own icon." if app.get("icon") else "It has the default icon: choose one in %s." % icon_place))
    last = state.get("version_code")
    code = app.get("version_code", "")
    if last is None:
        out.append((None, "Version %s (number %s). Nothing was published from here yet." % (app.get("version_name", ""), code)))
    elif str(code).isdigit() and int(code) > int(last):
        out.append((True, "Version %s (number %s). The last one signed was number %s." % (app.get("version_name", ""), code, last)))
    else:
        out.append((False, "The version number is still %s, the same as the last one signed. A phone or the Play Store refuses that: press Next version." % code))
    try:
        jks, _ = key_files(app.get("application_id", ""))
    except ImportError:
        jks = ""
    if jks and os.path.isfile(jks):
        saved = state.get("key_saved")
        out.append((bool(saved), "The signing key has a copy, made %s." % saved if saved else "The signing key has no copy. If you lose it, you can never update this game: press Save a copy of the key."))
    else:
        out.append((None, "The signing key is made with the first signed version."))
    return out


class Runner:
    """One command at a time, with what it says going to a text box."""

    def __init__(self, widget, log, finished):
        self.widget, self.log, self.finished = widget, log, finished
        self.process = None
        self.lines = queue.Queue()
        self.said = []

    @property
    def busy(self):
        return self.process is not None and self.process.poll() is None

    def run(self, title, args, root):
        if self.busy:
            return False
        # APKPY_RELOAD=0: these commands build and install, they never need ApkPy's hot reload, and in a venv on
        # Windows ApkPy 1.14.2's reload starts copies of the app without end
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", APKPY_RELOAD="0")
        self.said = []
        self.title = title
        self.log(title + "\n", "head")
        self.process = subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self.read, args=(self.process,), daemon=True).start()
        self.widget.after(80, self.tick)
        return True

    def read(self, process):
        for line in process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def tick(self):
        ended = False
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    ended = True
                    break
                self.said.append(line)
                self.log(line)
        except queue.Empty:
            pass
        if ended:
            code = self.process.wait()
            self.process = None
            self.finished(self.title, code, "".join(self.said))
        else:
            self.widget.after(80, self.tick)

    def stop(self):
        """With what it started: `apkpy logs` leaves an adb running otherwise."""
        if self.busy:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True)
            else:
                self.process.kill()


class PublishScreen(tk.Frame):
    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.last_file = ""
        self.pending_explain = None
        self.build()
        self.refresh()

    def build(self):
        left = Scrolling(self, width=px(self, 500))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        body = tk.Frame(left.inner, padx=px(self, 12), pady=px(self, 8))
        body.pack(fill="x")

        tk.Label(body, text="Before you publish", font=("", 12, "bold")).pack(anchor="w")
        self.check_lines = tk.Frame(body)
        self.check_lines.pack(anchor="w", fill="x", pady=(px(self, 2), px(self, 4)))
        row = tk.Frame(body)
        row.pack(anchor="w", pady=(0, px(self, 12)))
        tk.Button(row, text="Next version", command=self.bump).pack(side="left", padx=(0, px(self, 4)))
        tk.Button(row, text="Save a copy of the key...", command=self.save_key).pack(side="left")

        tk.Label(body, text="On your phone", font=("", 12, "bold")).pack(anchor="w")
        self.device_label = tk.Label(body, text="", fg=MUTED, justify="left", wraplength=px(self, 470))
        self.device_label.pack(anchor="w")
        row = tk.Frame(body)
        row.pack(anchor="w", pady=px(self, 3))
        tk.Button(row, text="Install it", command=self.install).pack(side="left", padx=(0, px(self, 3)))
        tk.Button(row, text="Open it", command=self.open_on_phone).pack(side="left", padx=(0, px(self, 3)))
        tk.Button(row, text="See what it says", command=self.logs).pack(side="left", padx=(0, px(self, 3)))
        tk.Button(row, text="Look for a phone", command=self.refresh_device).pack(side="left", padx=(0, px(self, 3)))
        tk.Button(row, text="Uninstall...", command=self.uninstall).pack(side="left")

        tk.Label(body, text="A file", font=("", 12, "bold")).pack(anchor="w", pady=(px(self, 12), 0))
        for text, hint, command in (("Test version (.apk)", "To try it and share with friends. It installs over other test versions.", self.make_test),
                                    ("Signed version (.apk)", "To give to people. Updates must use the same key.", self.make_signed),
                                    ("For the Play Store (.aab)", "To upload in the Google Play Console.", self.make_store)):
            row = tk.Frame(body)
            row.pack(anchor="w", fill="x", pady=1)
            tk.Button(row, text=text, width=24, command=command).pack(side="left")
            tk.Label(row, text=hint, fg=MUTED, wraplength=px(self, 270), justify="left").pack(side="left", padx=px(self, 6))
        row = tk.Frame(body)
        row.pack(anchor="w", pady=px(self, 3))
        self.file_label = tk.Label(row, text="", fg=MUTED, wraplength=px(self, 330), justify="left")
        self.file_label.pack(side="left")
        self.show_button = tk.Button(row, text="Show the file", command=self.show_file)

        tk.Label(body, text="This computer", font=("", 12, "bold")).pack(anchor="w", pady=(px(self, 12), 0))
        tk.Label(body, text="Making an app needs Java and the Android tools.", fg=MUTED).pack(anchor="w")
        row = tk.Frame(body)
        row.pack(anchor="w", pady=px(self, 3))
        tk.Button(row, text="Check it", command=self.doctor).pack(side="left", padx=(0, px(self, 3)))
        tk.Button(row, text="Install what is missing...", command=self.setup).pack(side="left")

        right = tk.Frame(self, padx=px(self, 6), pady=px(self, 8))
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right)
        top.pack(fill="x")
        tk.Label(top, text="What it says", font=("", 12, "bold")).pack(side="left")
        tk.Button(top, text="Stop", command=self.stop).pack(side="right")
        self.result = tk.Label(right, text="", anchor="w", justify="left", wraplength=px(self, 560))
        self.result.pack(fill="x")
        box = tk.Frame(right)
        box.pack(fill="both", expand=True)
        self.text = tk.Text(box, wrap="word", font=("Consolas", 9), state="disabled")
        bar = ttk.Scrollbar(box, command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("head", font=("Consolas", 9, "bold"), foreground=ACCENT)
        self.runner = Runner(self, self.write, self.command_ended)

    def write(self, line, tag=None):
        self.text.configure(state="normal")
        self.text.insert("end", line, tag or ())
        self.text.see("end")
        self.text.configure(state="disabled")

    def refresh(self):
        self.show_checks()
        self.refresh_device()

    def reload(self):
        self.refresh()

    def show_checks(self):
        for child in self.check_lines.winfo_children():
            child.destroy()
        for good, words in checks(self.project, self.shell.problems_only(), getattr(self.shell, "ICON_PLACE", "My game")):
            colour, mark = (GOOD, "ok") if good else (MUTED, "-") if good is None else (LOOK_AHEAD, "!")
            line = tk.Frame(self.check_lines)
            line.pack(anchor="w", fill="x")
            tk.Label(line, text=mark, fg=colour, width=3, font=("", 9, "bold")).pack(side="left", anchor="n")
            tk.Label(line, text=words, fg=colour if good is False else "#22252b", anchor="w", justify="left", wraplength=px(self, 440)).pack(side="left")

    # ── the phone ──

    def adb(self):
        """It comes with the Android SDK, which is usually not on the PATH."""
        from .. import _host
        if not hasattr(self, "adb_path"):
            self.adb_path = _host.find_adb()
        return self.adb_path

    def devices(self):
        adb = self.adb()
        if not adb:
            return []
        try:
            said = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=8).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        return [line.split("\t")[0] for line in said.splitlines()[1:] if line.endswith("\tdevice")]

    def refresh_device(self):
        found = self.devices()
        if found:
            self.device_label.config(text="Connected: %s" % ", ".join(found), fg=GOOD)
        else:
            self.device_label.config(text="No phone found. Connect it with a USB cable, turn on USB debugging in the phone's developer options, and accept the question on its screen.", fg=MUTED)
        return found

    def command(self, title, *args):
        self.shell.save_all()
        self.result.config(text="")
        self.show_button.pack_forget()
        if not self.runner.run(title, [sys.executable, "-c", START] + list(args), self.project.root):
            self.result.config(text="Something is still running. Wait for it, or press Stop.", fg=LOOK_AHEAD)
            return False
        return True

    def install(self):
        if not self.refresh_device():
            self.result.config(text="No phone found.", fg=BAD)
            return
        self.command("Making it and installing it on the phone...", "run", "--usb")

    def app_id(self):
        return self.project.app.values.get("application_id", "")

    def open_on_phone(self):
        adb = self.adb()
        if not adb or not self.refresh_device():
            self.result.config(text="No phone found.", fg=BAD)
            return
        component = "%s/com.apkpy.app.Screen_homeActivity" % self.app_id()
        r = subprocess.run([adb, "shell", "am", "start", "--user", "0", "-n", component], capture_output=True, text=True, timeout=15)
        said = (r.stdout + r.stderr).strip()
        self.write(said + "\n")
        self.result.config(text="Not there yet: install it first." if "Error" in said else "It is opening on the phone.", fg=BAD if "Error" in said else GOOD)

    def uninstall(self):
        adb = self.adb()
        if not adb or not self.refresh_device():
            self.result.config(text="No phone found.", fg=BAD)
            return
        if not messagebox.askyesno("Uninstall", "Uninstall %s from the phone?\n\nIts saved games on that phone are lost." % self.app_id(), parent=self):
            return
        r = subprocess.run([adb, "uninstall", self.app_id()], capture_output=True, text=True, timeout=30)
        self.write((r.stdout + r.stderr).strip() + "\n")
        self.result.config(text="Uninstalled." if "Success" in r.stdout else "It was not uninstalled: see what it says.", fg=GOOD if "Success" in r.stdout else BAD)

    def logs(self):
        if self.refresh_device():
            self.command("What the game says on the phone, as it runs. Press Stop to end.", "logs")
        else:
            self.result.config(text="No phone found.", fg=BAD)

    # ── files ──

    def make_test(self):
        self.command("Making a test version...", "run")

    def ask_version(self):
        """A signed version with the number of the last one is refused later, so ask now."""
        last = read_state(self.project.root).get("version_code")
        code = self.project.app.values.get("version_code", "")
        if last is not None and str(code) == str(last):
            return messagebox.askyesno("The same version", "The last signed version was also number %s. A phone or the Play Store refuses that as an update.\n\nMake it anyway?" % code, parent=self)
        return True

    def make_signed(self):
        if self.ask_version():
            self.command("Making a signed version...", "release")

    def make_store(self):
        if self.ask_version():
            self.command("Making a version for the Play Store...", "release", "--aab")

    def command_ended(self, title, code, said):
        m = re.search(r"(?:Signed \w+ ready|APK ready|AAB ready):\s*(.+?)\s+\(\d+ KB\)", said)
        if m:
            self.last_file = m.group(1).strip()
            self.file_label.config(text=self.last_file)
            self.show_button.pack(side="left", padx=px(self, 6))
        if "Signed" in said and m:
            write_state(self.project.root, version_code=self.project.app.values.get("version_code"))
            self.file_label.config(text=self.last_file)
        self.explain(title, code, said, bool(m))
        self.show_checks()

    def explain(self, title, code, said, made):
        if "install failed" in said or "failed to install" in said or "INSTALL_FAILED" in said:
            if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in said or "signatures do not match" in said.lower():
                words = "The phone has this game with another key: a signed version and a test version cannot install over each other. Press Uninstall to remove the one on the phone, which loses its saved games, and try again."
            elif "INSTALL_FAILED_VERSION_DOWNGRADE" in said:
                words = "The phone has a newer version of this game. Press Next version, or Uninstall the one on the phone."
            else:
                words = "It was made, but the phone refused it: see what it says."
            self.result.config(text=words, fg=BAD)
        elif "USB: installed" in said:
            self.result.config(text="Installed. Press Open it, or find it on the phone.", fg=GOOD)
        elif "USB: no device" in said:
            self.result.config(text="It was made, but no phone was found.", fg=LOOK_AHEAD)
        elif made:
            self.result.config(text="Done.", fg=GOOD)
        elif code or "APKPY " in said or "APKPYGAME " in said:
            self.result.config(text="It stopped: read what it says.", fg=BAD)
        else:
            self.result.config(text="Finished.", fg=MUTED)

    def show_file(self):
        if self.last_file and os.path.exists(self.last_file):
            try:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self.last_file)])
            except OSError:
                self.result.config(text=self.last_file)

    def stop(self):
        self.runner.stop()

    def bump(self):
        app = self.project.app
        app.values["version_name"], app.values["version_code"] = next_version(app.values)
        self.shell.content_changed()
        self.shell.save_all()
        self.show_checks()
        screen = self.shell.screens.get("game")
        if screen is not None:
            screen.show_row()

    def save_key(self):
        folder = filedialog.askdirectory(parent=self, title="A safe place for the signing key: not inside this project")
        if folder:
            self.copy_key_to(folder)

    def copy_key_to(self, folder):
        try:
            made = copy_key(self.app_id(), folder)
        except (ValueError, OSError) as e:
            self.result.config(text=str(e), fg=BAD)
            return False
        write_state(self.project.root, key_saved=time.strftime("%Y-%m-%d"))
        self.result.config(text="Copied to %s. These two files have your key and its password: keep them safe and private, and never share them." % folder, fg=GOOD)
        self.write("\n".join(made) + "\n")
        self.show_checks()
        return True

    def doctor(self):
        self.result.config(text="")
        self.runner.run("Checking this computer...", [sys.executable, "-c", START, "doctor"], self.project.root)

    def setup(self):
        if messagebox.askyesno("Install what is missing", "This downloads Java, Gradle and the Android tools that are missing into a folder of your user (.apkpy). It can be a few gigabytes and take a while.\n\nGo on?", parent=self):
            self.runner.run("Installing what is missing...", [sys.executable, "-c", START, "setup"], self.project.root)


class HelpScreen(tk.Frame):
    """The guides of this project, read here. Links between them work."""

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell = shell
        self.root_folder = shell.project.root
        self.pages = self.find_pages()
        left = tk.Frame(self, width=px(self, 250), padx=px(self, 8), pady=px(self, 8))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="Help", font=("", 12, "bold")).pack(anchor="w")
        self.items = tk.Listbox(left, activestyle="none", exportselection=False)
        self.items.pack(fill="both", expand=True, pady=(px(self, 4), 0))
        for title, _ in self.pages:
            self.items.insert("end", title)
        self.items.bind("<<ListboxSelect>>", lambda e: self.pick())
        box = tk.Frame(self, pady=px(self, 8))
        box.pack(side="left", fill="both", expand=True, padx=(0, px(self, 8)))
        self.text = tk.Text(box, wrap="word", font=("", 10), padx=px(self, 14), pady=px(self, 10), state="disabled", cursor="arrow", spacing1=2, spacing3=3)
        bar = ttk.Scrollbar(box, command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("h1", font=("", 16, "bold"), spacing3=6)
        self.text.tag_configure("h2", font=("", 12, "bold"), spacing1=10, spacing3=3)
        self.text.tag_configure("h3", font=("", 10, "bold"), spacing1=8)
        self.text.tag_configure("code", font=("Consolas", 9), background="#eef0f3")
        self.text.tag_configure("bold", font=("", 10, "bold"))
        self.text.tag_configure("link", foreground=ACCENT, underline=True)
        self.text.tag_bind("link", "<Enter>", lambda e: self.text.configure(cursor="hand2"))
        self.text.tag_bind("link", "<Leave>", lambda e: self.text.configure(cursor="arrow"))
        self.links = 0
        if self.pages:
            self.show(0)

    def find_pages(self):
        pages = []
        folder = os.path.join(self.root_folder, "tutorial")
        if os.path.isfile(os.path.join(folder, "studio.md")):
            pages.append(("The Studio", os.path.join(folder, "studio.md")))
        else:
            pages.append(("The Studio", GUIDE))
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name[0].isdigit() and name.endswith(".md"):
                    pages.append((self.first_line(os.path.join(folder, name)), os.path.join(folder, name)))
        if os.path.isfile(os.path.join(self.root_folder, "README.md")):
            pages.append(("Everything, by hand (README)", os.path.join(self.root_folder, "README.md")))
        return pages

    @staticmethod
    def first_line(path):
        with open(path, encoding="utf-8") as fh:
            return fh.readline().strip().lstrip("# ") or os.path.basename(path)

    def pick(self):
        chosen = self.items.curselection()
        if chosen:
            self.show(chosen[0])

    def show(self, at):
        self.items.selection_clear(0, "end")
        self.items.selection_set(at)
        self.current_path = self.pages[at][1]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        with open(self.current_path, encoding="utf-8") as fh:
            self.render(fh.read())
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def render(self, text):
        in_code = False
        for line in text.split("\n"):
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                self.text.insert("end", "  " + line + "\n", "code")
            elif line.startswith("### "):
                self.text.insert("end", line[4:] + "\n", "h3")
            elif line.startswith("## "):
                self.text.insert("end", line[3:] + "\n", "h2")
            elif line.startswith("# "):
                self.text.insert("end", line[2:] + "\n", "h1")
            elif re.match(r"\|[\s:-]+\|", line):
                continue
            elif line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                self.inline("  " + "  |  ".join(cells))
            else:
                self.inline(line)

    def inline(self, line):
        """**bold**, `code` and [links](file)."""
        for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))", line):
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                self.text.insert("end", part[2:-2], "bold")
            elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                self.text.insert("end", part[1:-1], "code")
            elif part.startswith("["):
                m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
                self.link(m.group(1), m.group(2))
            else:
                self.text.insert("end", part)
        self.text.insert("end", "\n")

    def link(self, words, target):
        path = os.path.normpath(os.path.join(os.path.dirname(self.current_path), target))
        at = next((i for i, (_, p) in enumerate(self.pages) if os.path.normpath(p) == path), None)
        if at is None:
            self.text.insert("end", words)
            return
        self.links += 1
        tag = "link%d" % self.links
        self.text.tag_bind(tag, "<Button-1>", lambda e, i=at: self.show(i))
        self.text.insert("end", words, ("link", tag))

    def reload(self):
        pass
