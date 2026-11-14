"""The source, read: screens, components and functions, as commands to write from.

One class, MultiScreenTranspiler, written over these modules; each holds the methods that read one thing:

    arguments     What a call was given, and the app's functions it names as callbacks.
    first_pass    Read from the whole file before any screen: drawer, overlays, pins, translations, numbers.
    bars          The app bar, the drawer, sheets and dialogs, fonts.
    components    A component of a screen, with its arguments: button(), card(), list_view() and the rest.
    statements    The lines of a function of the app, each as a command.
    calls         A call on a line of its own: a message, the map, storage, the phone, the network, audio.
    view_calls    A call that changes the screen: a component's method, a list's items, a dialog, a screen.
    module_level  The top of the app's file: functions, assignments, ifs, and the calls that make screens.
"""
import ast

from ...features import data as data_feature
from ...features import jobs as jobs_feature
from .... import fonts as _fonts

from .arguments import ArgumentReader
from .first_pass import FirstPass
from .bars import BarReader
from .components import ComponentReader
from .statements import StatementReader
from .calls import CallReader
from .view_calls import ViewCallReader
from .module_level import ModuleReader


class MultiScreenTranspiler(
        ArgumentReader, FirstPass, BarReader, ComponentReader, StatementReader, CallReader,
        ViewCallReader, ModuleReader, ast.NodeVisitor):
    """
    Analisa código Python com Screens e constrói um modelo de dados
    que depois é usado para gerar múltiplos ficheiros Java/XML.
    """

    def __init__(self, styles=None):
        self.styles = styles or {}
        # var_name (Python) -> screen_id
        self.screens = {}
        self.screen_bg_images = {}
        # screen_id -> bool (scroll=True)
        self.screen_scroll = {}
        # screen_id -> "portrait" / "landscape" / "auto", and run(orientation=)
        # for the screens that say nothing.
        self.screen_orientation = {}
        self.app_orientation = None
        # screen_id -> lista de dicts de componentes
        self.screen_components = {}
        # screen_id -> fixed/collapsible app bar metadata. App bars are screen
        # chrome and deliberately stay outside the scrolling component tree.
        self.screen_app_bars = {}
        # Declarative overlays (bottom sheets, modals, menus and pickers).
        # They are detached from screen layout and materialized only on open().
        self.overlays = {}
        # var_name -> dict do componente (para resolver on_click_navigate)
        self.component_vars = {}
        # lista de {from_screen_id, button_py_var, to_screen_id}
        self.navigations = []
        self.start_screen_id = None
        self.functions = {}
        # Preenchidos por prescan_numeric_args; vazios significam "toda a
        # gente é texto", que era o comportamento anterior.
        self.numeric_params = {}
        self.numeric_returns = {}
        # Observable values declared with state(...). The generated Android
        # runtime keeps them process-wide so navigation does not lose data.
        self.reactive_states = {}
        # screen_id -> lifecycle callbacks (on_mount/resume/pause/destroy).
        self.screen_lifecycles = {}
        # Screens asked to block screenshots. None means every screen.
        self.secure_screens = None
        self.has_secure_screen = False
        self.declared_permissions = []
        self.permission_callbacks = {}
        # Comandos de inicialização a nível de módulo (storage.get + set_value no topo)
        self.module_init_cmds = []
        # Constantes de string definidas a nível de módulo (ex: API_KEY = "...")
        self.string_constants = {}
        # Funções usadas como callbacks assíncronos cujo 1.º argumento é sempre
        # boolean (https.get/post on_response, camera.capture/gallery.pick on_result,
        # permissions.request on_response) — independentemente do nome que o utilizador
        # der ao parâmetro (ex: "sucesso", "ok", "feito", ...).
        self.boolean_first_arg_callbacks = set()
        # Background services declarados via service.every(run=fn, minutes=N, id="...")
        self.background_services = []
        # Tarefas únicas atrasadas declaradas via service.once(run=fn, after_minutes=N, id="...")
        self.onetime_services = []
        # Listas literais definidas a nível de módulo — name -> ast.List node
        self.list_assignments = {}
        self.dict_assignments = {}
        # Nomes dessas listas que a app MUDA em runtime (x.append(...)).
        # Uma lista de módulo é normalmente inlinada como literal, o que está
        # certo enquanto ninguém lhe mexe. A partir do momento em que alguém
        # lhe faz append, o literal passaria a mentir: o Python vê a lista a
        # crescer e o Java continuava a ler a de origem. Essas — e só essas —
        # passam a viver no estado partilhado, que é uma só por processo,
        # como o próprio módulo Python.
        self.mutated_lists = set()
        # As palavras da app: tag -> {chave: texto}, e a lingua de
        # res/values/, que e a que o telemovel usa como recuo.
        self.translations = {}
        # Hosts com certificado fixado: host -> {pins, expires, subdomains}
        self.pinned_hosts = {}
        self.default_language = ''
        # Typefaces declaradas com font(...) — o mesmo registo que o
        # Previewer usa, mas preenchido a partir da AST.
        self.fonts = _fonts.FontRegistry()
        # Bottom navigation bar config (ou None)
        self.bottom_nav = None
        # Navigation drawer (ou None) e o nome da variavel que o guarda,
        # para reconhecer menu.open() dentro de um comando.
        self.drawer = None
        self.drawer_var = None
        # Barra "now playing" (audio.now_playing) — {'progress': pyvar, 'time': pyvar|None}
        self.now_playing = None
        # Local pictures named only in image.set_src("...") calls: they are
        # packaged like the src of an image() so the phone can show them.
        self.set_src_assets = set()
        # Commands inside a row= that take the row's item.
        self._row_item_callbacks = set()
        # Local audio named in audio.play("...") or a playlist's sources: it
        # goes into res/raw. It used to reach the phone as a bare file name
        # the media player could not open -- a player stuck at 0:00.
        self.audio_assets = set()
        # Botões que refletem o estado do leitor (audio.controls) — play/pause toggle,
        # shuffle on/off, repeat off/all/one. {'play_pause': pyvar, 'shuffle': pyvar, ...textos}
        self.audio_controls = None
        # Like/guardar (audio.like_button) — {'button': pyvar, 'liked': '❤️', 'unliked': '🤍'};
        # o botão guarda/remove a faixa atual nos favoritos (SharedPreferences) e reflete o estado.
        self.audio_like = None
        # Lista de músicas guardadas (audio.liked_list) — py_var do list_view a encher dos favoritos.
        self.audio_liked_list = None
        # Lista de playlists do utilizador (audio.playlists_list) — py_var do list_view
        # a encher com os nomes das playlists (criar/gerir playlists).
        self.audio_playlists_list = None
        # Editor de playlist (audio.playlist_editor) — py_var do list_view que mostra as
        # faixas da playlist em edição (audio.edit_playlist); tocar numa remove-a.
        self.audio_playlist_editor = None
        # Login OAuth (auth.login) — config global: provider, client_id, urls, redirect,
        # scopes, ecrã `then`. Gera a ApkpyAuthActivity (recebe o deep-link + troca token).
        self.auth = None
        # Mini-player fixo (mini_player) — barra ancorada no fundo de TODOS os ecrãs
        # que mostra a faixa atual (capa+título+play/pause) lendo o media service.
        self.mini_player = None
        # on_click de list_view ricos: o `item` é JSON → item["k"] usa _jsonGet
        self.json_item_callbacks = set()
        self._implicit_card_count = 0
        self._implicit_state_count = 0
        self._upload_command_count = 0
        self._websocket_command_count = 0
        # Configuration consumed by the isolated remote-push generator.
        self.push_config = None
        # Typed SQLite declarations/commands live in an isolated feature module.
        data_feature.initialize(self)
        # Persistent background jobs (background_job → WorkManager).
        jobs_feature.initialize(self)
