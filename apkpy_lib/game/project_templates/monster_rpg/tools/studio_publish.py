"""The Publish and Help sections of the Studio. They are ApkPy's own now (apkpy_lib.game.studio.publish), shared by
every game's Studio; this name stays for the template's tools.
"""
from apkpy_lib.game.studio import publish as _publish
from apkpy_lib.game.studio.publish import (GUIDE, LOOK_AHEAD, PLACEHOLDER_ID, START, STATE_FILE, HelpScreen,  # noqa: F401
                                           PublishScreen, Runner, copy_key, key_files, next_version, read_state, write_state)


def checks(project, problems=()):
    """What to look at before publishing: [(good: True, False or None for a remark, words)]. Here the icon is
    chosen in Title and icon."""
    return _publish.checks(project, problems, "Title and icon")
