"""Where the game examples are: examples/games/ of ApkPy's repository.

Working in ApkPy's own development tree, the examples live in its copy of the public repository
(github-repo/repo-apkpy/examples), the same place tests/features/_layout.py looks.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository


def examples(*parts):
    for base in (os.path.join(ROOT, "examples"), os.path.join(ROOT, "github-repo", "repo-apkpy", "examples")):
        if os.path.isdir(base):
            return os.path.join(base, "games", *parts)
    return os.path.join(ROOT, "examples", "games", *parts)
