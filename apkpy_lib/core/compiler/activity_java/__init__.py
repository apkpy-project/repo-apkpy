"""A screen's Activity.

One class, ActivityJava, written over these modules; each holds the methods of one part of the work:

    screen      What is on the screen and what the app does with it: the questions every other part asks.
    values      A value of the app, written as Java: a name, a call, a field's text, an item of a list.
    commands    What a function of the app does, command by command, written as Java statements.
    feeds       virtual_collection: its adapter, and the commands that add, change and take rows.
    components  Each component of the screen, found and made ready in onCreate.
    class_head  The top of the Java file: imports, the class line, its fields, and the methods every screen has.
    on_create   onCreate, from its first line to its last.
    functions   The app's functions, each as a method of the Activity, and the methods that draw its state.
    lifecycle   onDestroy, the answer to a permission, onPause and onResume.
    helpers     The Java methods the commands call: favourites, playlists, https, JSON, sharing, audio, sign-in.
    device      The Java methods that reach the phone: uploads, installed apps, pickers, location, pictures.
    overlays    The drawer, the sheets and dialogs, and the last lines of the class.

write() calls the parts in the order the Java file is written. A method that starts with _write or
_open or _close appends to self.lines; the others answer what it asks.
"""
import functools

from ...features import view_state as view_state_feature

from .screen import ScreenFacts
from .values import Values
from .commands import Commands
from .feeds import Feeds
from .components import Components
from .class_head import ClassHead
from .on_create import OnCreate
from .functions import Functions
from .lifecycle import Lifecycle
from .helpers import Helpers
from .device import Device
from .overlays import Overlays


class ActivityJava(
        ScreenFacts, Values, Commands, Feeds, Components, ClassHead, OnCreate, Functions, Lifecycle,
        Helpers, Device, Overlays):
    """One screen's Activity, being written.

    What the function this was kept in its local variables is here: what __init__ is handed and makes
    ready, what each part works out for the ones after it, and `lines`, the Java file so far.
    """

    def __init__(self, screen_id, components, navigations, start_screen_id, package='com.apkpy.app',
                 functions_map=None, declared_permissions=None, permission_callbacks=None,
                 styles=None, module_init_cmds=None, string_constants=None,
                 background_services=None, onetime_services=None, boolean_first_arg_callbacks=None,
                 scroll=False, bottom_nav_info=None, drawer_info=None, now_playing=None,
                 json_item_callbacks=None, audio_controls=None, auth=None, mini_player=None,
                 audio_like=None, audio_liked_list=None, audio_playlists_list=None,
                 audio_playlist_editor=None, app_bar_info=None, overlays=None, reactive_states=None,
                 lifecycle_info=None, data_observers=None, job_observers=None, secure_screen=False):
        self.screen_id = screen_id
        self.components = components
        self.navigations = navigations
        self.start_screen_id = start_screen_id
        self.package = package
        self.module_init_cmds = module_init_cmds
        self.string_constants = string_constants
        self.background_services = background_services
        self.onetime_services = onetime_services
        self.boolean_first_arg_callbacks = boolean_first_arg_callbacks
        self.scroll = scroll
        self.bottom_nav_info = bottom_nav_info
        self.drawer_info = drawer_info
        self.now_playing = now_playing
        self.audio_controls = audio_controls
        self.auth = auth
        self.mini_player = mini_player
        self.audio_like = audio_like
        self.audio_liked_list = audio_liked_list
        self.audio_playlists_list = audio_playlists_list
        self.audio_playlist_editor = audio_playlist_editor
        self.app_bar_info = app_bar_info
        self.secure_screen = secure_screen
        self.lines = []      # the Java file, a line at a time: every method writes to it
        # _val_to_java is handed to the writers of conditions and loops, and they ask it for .numeric,
        # .bool_names and .kind_of. A method bound to the object cannot be given those; this can.
        self._val_to_java = functools.partial(type(self)._val_to_java, self)
        self.json_item_callbacks = json_item_callbacks or set()
        self._vc_ink_cache = {}      # _ink_parent_backgrounds of this screen, worked out once

        self.class_name = f"Screen_{screen_id}Activity"
        self.functions_map = functions_map or {}
        self.declared_permissions = declared_permissions or []
        self.permission_callbacks = permission_callbacks or {}
        self.styles = styles or {}
        self.overlays = overlays or {}
        self.reactive_states = reactive_states or {}
        self.lifecycle_info = lifecycle_info or {}
        self.all_data_observers = list((data_observers or {}).values())
        # background_job(...).observe(on_change=..., screen=...) for this screen.
        self.screen_job_observers = [
            item for item in (job_observers or [])
            if item.get('screen_id') in (None, screen_id)
        ]
        self.screen_data_observers = [
            item for item in self.all_data_observers
            if item.get('screen_id') == screen_id
        ]
        # Nomes de args boolean do callback que está a ser gerado agora;
        # atualizado antes de cada pythonCallback_X para que _gen_cmds/_gen_cmds_local
        # possam passar os nomes certos a _cond_to_java.
        self._cur_bool_args = [set()]
        self.all_comps_flat = list(self._all_comps(components))
        self.has_saved_text = view_state_feature.used_by(
            self.all_comps_flat, self.functions_map, module_init_cmds,
        )

    def write(self):
        """The Java file, from its first line to its last."""
        self._number_the_components()
        self._see_what_is_used()
        self._collect_imports()
        self._write_fields()
        self._write_launchers()
        self._write_shared_methods()
        self._open_on_create()
        self._write_components()
        self._write_first_commands()
        self._write_listeners()
        self._write_player_controls()
        self._close_on_create()
        self._write_state_methods()
        self._write_destroy_and_permissions()
        self._write_functions()
        self._write_pause_and_resume()
        self._write_favourites_and_playlists()
        self._write_https_and_json()
        self._write_sharing_audio_sign_in()
        self._write_uploads()
        self._write_apps_and_pickers()
        self._write_location_and_images()
        self._write_drawer_and_overlays()
        return self._write_dialogs_and_close()


def _generate_activity_java(*args, **kwargs):
    """Gera o conteúdo completo de um ficheiro *Activity.java para um Screen.

    The arguments are the ones of ActivityJava.
    """
    return ActivityJava(*args, **kwargs).write()
