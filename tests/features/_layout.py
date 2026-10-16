"""Where the files some tests read are.

The repository is laid out one way where it is published -- examples/ beside
apkpy_lib/ -- and another in the tree it is developed in, and the source of
the site is only in the second. A test asks here and skips when the answer
is None, so the suite passes in either.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _first(*folders):
    return next((folder for folder in folders if folder.is_dir()), None)


def examples():
    """The folder of numbered examples, or None."""
    return _first(ROOT / "examples", ROOT / "github-repo" / "repo-apkpy" / "examples")


def site_docs():
    """The source of the site's pages, or None."""
    return _first(ROOT / "website" / "docs")
