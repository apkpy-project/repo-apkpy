"""Write the story in a window: colours, buttons for each kind of line, and problems as you type.

    python tools/story_editor.py

The map editor opens it too, on the event of the object you selected. It reads and writes story/*.story.
"""
import os
import re
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import story_tool  # noqa: E402
from studio_ui import make_root, px  # noqa: E402

KEYWORDS = r"^\s*(say|ask|if|once|otherwise:|yes:|no:|set|clear|give|heal|open|shop|battle|warp|step_back|end|before:|won:|after:)(?=\s|$)"
SNIPPETS = (
    ("say", ["say Write it here."]),
    ("ask", ["ask Write the question here?", "yes:", "    say Yes.", "no:", "    say No."]),
    ("once", ["once my_flag:", "    say Only the first time.", "otherwise:", "    say Every other time."]),
    ("if", ["if my_flag:", "    say With that flag.", "otherwise:", "    say Without it."]),
    ("set flag", ["set my_flag"]),
    ("give", ["give tonic 1"]),
    ("heal", ["heal"]),
    ("shop", ["shop harbour"]),
    ("battle", ["battle tess"]),
)


def skeleton(event_id):
    if event_id.startswith("trainer."):
        return "trainer %s\n    before:\n        say Write what they say first.\n    won:\n        say Write what they say when they lose.\n    after:\n        say Write what they say from then on.\n" % event_id[8:]
    return "event %s\n    say Write what happens here.\n" % event_id


class StoryPanel(tk.Frame):
    """The story editor, inside any window."""

    def __init__(self, parent, on_saved=None, test_event=None):
        tk.Frame.__init__(self, parent)
        self.on_saved = on_saved
        self.test_event = test_event
        self.read_files()
        self.current = None
        self.job = None
        self.problem_at = None
        self.loading = False
        self.build()
        self.show_files()
        if self.texts:
            self.open_file(sorted(self.texts)[0])
        self.check()

    def read_files(self):
        self.texts, self.saved = {}, {}
        for name in self.file_names():
            with open(os.path.join(story_tool.SOURCE, name), encoding="utf-8") as fh:
                self.texts[name] = fh.read()
            self.saved[name] = self.texts[name]

    def reload_files(self):
        """The files changed outside: see them again."""
        keep = self.current
        self.current = None
        self.read_files()
        self.show_files()
        if self.texts:
            self.open_file(keep if keep in self.texts else sorted(self.texts)[0])
        self.check()

    def go_to(self, target):
        self.open_event(target)

    def event_here(self):
        """The event the cursor is in."""
        at = int(self.text.index("insert").split(".")[0])
        lines = self.text.get("1.0", "end-1c").split("\n")
        for number in range(min(at, len(lines)) - 1, -1, -1):
            m = re.match(r"(event|trainer) +(\S+)", lines[number])
            if m:
                return m.group(2) if m.group(1) == "event" else "trainer." + m.group(2)
        return ""

    def test_this(self):
        event = self.event_here()
        if event:
            self.save()
            self.test_event(event)
        else:
            self.problem.config(text="Click inside an event first.", fg="#c02020")

    def find_word(self, word):
        """Goes to the first line that has this word."""
        self.keep_text()
        for name in sorted(self.texts):
            m = re.search(r"\b%s\b" % re.escape(word), self.texts[name])
            if m:
                self.open_file(name)
                self.go_to_line(self.texts[name].count("\n", 0, m.start()) + 1)
                return

    @staticmethod
    def file_names():
        os.makedirs(story_tool.SOURCE, exist_ok=True)
        return sorted(n for n in os.listdir(story_tool.SOURCE) if n.endswith(".story"))

    def build(self):
        left = tk.Frame(self, padx=5, pady=4, width=px(self, 210))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="Files", font=("", 10, "bold")).pack(anchor="w")
        self.file_list = tk.Listbox(left, height=6, exportselection=False, activestyle="none")
        self.file_list.pack(fill="x")
        self.file_list.bind("<<ListboxSelect>>", lambda e: self.pick_file())
        tk.Button(left, text="New file...", command=self.new_file).pack(fill="x", pady=(2, 8))
        tk.Label(left, text="In this file", font=("", 10, "bold")).pack(anchor="w")
        self.outline = tk.Listbox(left, exportselection=False, activestyle="none")
        self.outline.pack(fill="both", expand=True)
        self.outline.bind("<<ListboxSelect>>", lambda e: self.pick_outline())
        tk.Button(left, text="New event...", command=self.new_event).pack(fill="x", pady=(2, 0))

        bottom = tk.Frame(self)
        bottom.pack(side="bottom", fill="x")
        self.problem = tk.Label(bottom, text="", anchor="w", justify="left", wraplength=px(self, 900), cursor="hand2")
        self.problem.pack(side="left", fill="x", expand=True, padx=6, pady=2)
        self.problem.bind("<Button-1>", lambda e: self.go_to_problem())

        top = tk.Frame(self, pady=3)
        top.pack(side="top", fill="x")
        tk.Label(top, text="Add:").pack(side="left")
        for label, lines in SNIPPETS:
            tk.Button(top, text=label, command=lambda l=lines: self.insert_snippet(l)).pack(side="left", padx=1)
        tk.Button(top, text="Save", command=self.save).pack(side="right", padx=4)
        if self.test_event is not None:
            tk.Button(top, text="Test this event", command=self.test_this).pack(side="right", padx=1)

        self.text = tk.Text(self, wrap="word", undo=True, font=("Consolas", 11), tabs=("1c",))
        bar = tk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("comment", foreground="#808080")
        self.text.tag_configure("head", foreground="#a03080", font=("Consolas", 11, "bold"))
        self.text.tag_configure("word", foreground="#2060c0")
        self.text.tag_configure("bad", background="#ffd8d8")
        self.text.bind("<<Modified>>", self.modified)
        self.text.bind("<Tab>", self.tab_key)

    # ── files ──

    def show_files(self):
        self.file_list.delete(0, "end")
        for name in sorted(self.texts):
            self.file_list.insert("end", name + (" *" if self.texts[name] != self.saved.get(name) else ""))
        if self.current in self.texts:
            self.file_list.selection_set(sorted(self.texts).index(self.current))

    def pick_file(self):
        chosen = self.file_list.curselection()
        if chosen:
            self.open_file(sorted(self.texts)[chosen[0]])

    def open_file(self, name):
        self.keep_text()
        self.current = name
        self.loading = True
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.texts[name])
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.loading = False
        self.paint()
        self.show_outline()
        self.show_files()

    def keep_text(self):
        if self.current is not None:
            self.texts[self.current] = self.text.get("1.0", "end-1c")

    def new_file(self):
        name = simpledialog.askstring("New file", "A name for the file, such as cave:", parent=self)
        if not name:
            return
        name = name.strip().replace(".story", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            messagebox.showinfo("New file", "A name is lowercase letters, numbers and _.", parent=self)
            return
        name += ".story"
        if name not in self.texts:
            self.keep_text()
            self.texts[name] = "# Write this part of the story here.\n"
            self.saved[name] = None
        self.open_file(name)

    def new_event(self):
        name = simpledialog.askstring("New event", "Its name, such as cave.old_man:", parent=self)
        if name and name.strip():
            self.open_event(name.strip())

    def open_event(self, event_id):
        """Shows the event, and writes a first version of it if it does not exist yet."""
        self.keep_text()
        self.winfo_toplevel().lift()
        pattern = self.head_pattern(event_id)
        for name in sorted(self.texts):
            if re.search(pattern, self.texts[name], re.M):
                self.open_file(name)
                self.go_to_head(pattern)
                return
        prefix = event_id.split(".")[0] + ".story"
        name = prefix if prefix in self.texts else self.current or (sorted(self.texts)[0] if self.texts else None)
        if name is None:
            name = "story.story"
            self.texts[name] = ""
            self.saved[name] = None
        self.texts[name] = self.texts[name].rstrip("\n") + "\n\n" + skeleton(event_id)
        self.current = None
        self.open_file(name)
        self.go_to_head(pattern)
        self.check()

    @staticmethod
    def head_pattern(event_id):
        if event_id.startswith("trainer."):
            return r"^trainer +%s\s*$" % re.escape(event_id[8:])
        return r"^event +%s\s*$" % re.escape(event_id)

    def go_to_head(self, pattern):
        text = self.text.get("1.0", "end-1c")
        m = re.search(pattern, text, re.M)
        if m:
            self.go_to_line(text.count("\n", 0, m.start()) + 1)

    def go_to_line(self, line):
        self.text.mark_set("insert", "%d.0" % line)
        self.text.see("%d.0" % line)
        self.text.focus_set()

    # ── editing ──

    def modified(self, event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self.loading:
            return
        self.keep_text()
        self.paint()
        self.show_files()
        if self.job is not None:
            self.after_cancel(self.job)
        self.job = self.after(350, self.check)

    def tab_key(self, event):
        self.text.insert("insert", "    ")
        return "break"

    def insert_snippet(self, lines):
        line = self.text.get("insert linestart", "insert lineend")
        if line.strip():
            indent = line[:len(line) - len(line.lstrip())]
            if line.rstrip().endswith(":") or re.match(r"(event|trainer) ", line):
                indent += "    "
            self.text.mark_set("insert", "insert lineend")
            prefix = "\n"
        else:
            indent = line or "    "
            self.text.delete("insert linestart", "insert lineend")
            prefix = ""
        self.text.insert("insert", prefix + "\n".join(indent + l for l in lines))
        self.text.focus_set()

    def paint(self):
        for tag in ("comment", "head", "word"):
            self.text.tag_remove(tag, "1.0", "end")
        for number, line in enumerate(self.text.get("1.0", "end-1c").split("\n"), 1):
            if line.lstrip().startswith("#"):
                self.text.tag_add("comment", "%d.0" % number, "%d.end" % number)
            elif re.match(r"(event|trainer) ", line):
                self.text.tag_add("head", "%d.0" % number, "%d.end" % number)
            else:
                m = re.match(KEYWORDS, line)
                if m:
                    self.text.tag_add("word", "%d.%d" % (number, m.start(1)), "%d.%d" % (number, m.end(1)))

    def show_outline(self):
        self.outline.delete(0, "end")
        self.heads = []
        for number, line in enumerate(self.text.get("1.0", "end-1c").split("\n"), 1):
            m = re.match(r"(event|trainer) +(\S+)", line)
            if m:
                self.heads.append(number)
                self.outline.insert("end", m.group(2) if m.group(1) == "event" else "trainer " + m.group(2))

    def pick_outline(self):
        chosen = self.outline.curselection()
        if chosen:
            self.go_to_line(self.heads[chosen[0]])

    # ── problems, saving ──

    def check(self):
        self.job = None
        self.keep_text()
        self.show_outline()
        self.problem_at = None
        self.text.tag_remove("bad", "1.0", "end")
        problem = story_tool.find_problem(self.texts)
        if not problem:
            self.problem.config(text="No problems in the story.", fg="#208040")
            return
        self.problem.config(text=problem, fg="#c02020")
        m = re.match(r"story/([\w.]+):(\d+)", problem)
        if m:
            self.problem_at = (m.group(1), int(m.group(2)))
            if m.group(1) == self.current:
                self.text.tag_add("bad", "%d.0" % self.problem_at[1], "%d.end" % self.problem_at[1])

    def go_to_problem(self):
        if self.problem_at:
            name, line = self.problem_at
            if name != self.current:
                self.open_file(name)
            self.go_to_line(line)

    def dirty(self):
        self.keep_text()
        return [n for n in self.texts if self.texts[n] != self.saved.get(n)]

    def save(self):
        for name in self.dirty():
            with open(os.path.join(story_tool.SOURCE, name), "w", encoding="utf-8") as fh:
                fh.write(self.texts[name])
            self.saved[name] = self.texts[name]
        self.show_files()
        self.check()
        if self.on_saved:
            self.on_saved()

    def close(self):
        """False when the person changed their mind. On its own, it closes its window."""
        if self.dirty():
            answer = messagebox.askyesnocancel("Save changes?", "Save the changes to the story?", parent=self)
            if answer is None:
                return False
            if answer:
                self.save()
        self.winfo_toplevel().destroy()
        return True


def open_window(parent, on_saved=None):
    """A window of its own, for the map editor when it is not inside the Studio."""
    window = tk.Toplevel(parent)
    window.title("Story")
    window.geometry("%dx%d" % (px(parent, 980), px(parent, 640)))
    panel = StoryPanel(window, on_saved)
    panel.pack(fill="both", expand=True)
    window.protocol("WM_DELETE_WINDOW", panel.close)
    window.bind("<Control-s>", lambda e: panel.save())
    return panel


def main():
    root = make_root("Story")
    root.geometry("%dx%d" % (px(root, 980), px(root, 640)))
    panel = StoryPanel(root)
    panel.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", panel.close)
    root.bind("<Control-s>", lambda e: panel.save())
    root.mainloop()


if __name__ == "__main__":
    main()
