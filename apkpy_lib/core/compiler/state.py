"""What one build knows about the app while it is being written.

Filled by the first read of the source and asked by everything after it. Every value is a container
changed in place, never a name bound again: the modules that import it all hold the same one.
"""


# A app le ou limpa relatorios de falha? Decidido a partir da AST, uma
# vez por transpilacao: o crash.last() e um VALOR dentro de uma
# atribuicao, nao um comando, e quem so olhasse para comandos deixava
# o handler por instalar no caso mais comum.
_USES_CRASH = [False]
_USES_SCAN = [False]
_SCAN_FORMATS = [()]
# flashlight.is_on()/available() are values, not commands, so an app whose
# only mention of the torch is `if flashlight.is_on():` still needs the
# shared class written. The command gate alone would not see it.
_USES_FLASHLIGHT = [False]
# sensors.available() and every battery.* are values too, so the same
# blind spot applies: an app whose only mention is `if battery.charging():`
# needs the runtime written even though no command asks for it.
_USES_SENSORS = [False]
# Which screen owns each component, and which components some code may
# write from another screen (pending_views.plan). Per transpilation.
_VIEW_OWNERS = [{}]
# Gradients: whether ApkpyGradient.java ships, and the screens' own drawables
# (written by _generate_layout_xml, which has no output_files of its own).
_USES_GRADIENT = [False]
# A textarea with syntax: in its CSS: ApkpyCodeColors.java ships.
_USES_CODE_EDITOR = [False]
# A box with shimmer: in its CSS: ApkpyShimmer.java ships.
_USES_SHIMMER = [False]
# Some screen has a web_page: the start screen warms the WebView up.
_WARM_WEB = [False]
_SCREEN_GRADIENTS = [{}]
_PENDING_TARGETS = [{}]
_VIEW_COMPS = [{}]

# As palavras da app, por transpilacao (o padrao do _APP_THEME).
# 'table' e tag -> {chave: texto}; 'default' e a lingua que vive em
# res/values/ e a que o telemovel responde quando nao tem a do aparelho.
_I18N = [{'table': {}, 'default': ''}]

# Todas as chaves sob as quais um comando pode guardar outra lista de comandos.
# Quem percorre a árvore de comandos tem de usar esta tupla: um corpo novo que
# umas passagens percorrem e outras não é como um callback dentro de um
# try/except deixa de ser recolhido e o método nunca chega a ser escrito.
_BODY_KEYS = ('true_body', 'false_body', 'body', 'handler', 'final')

# Listas de módulo que a app muda em runtime: nome -> JSON inicial, em texto.
# Preenchido no início de cada transpilação, como o _APP_THEME e o
# _TRANSPILE_FONTS, porque os dois geradores (Activity e Worker) vivem em
# âmbitos diferentes e teriam de receber isto por mais dois parâmetros numa
# assinatura que já tem quarenta.
_MUTATED_LISTS = [{}]
# Module-level list literals by name, so `x in NAMES` asks a list rather than
# searching the text of its JSON. Filled once the module has been visited.
_MODULE_LISTS = [{}]
# Module-level lists, tuples and dicts written out as literals, as the JSON
# text of their Java field. Without the field, len(ITEMS), ITEMS[0] or
# PRICES["tea"] inside a function named something no Java class declared, and
# the build stopped in Gradle, on a file nobody wrote.
_MODULE_STRUCT_TEXT = [{}]
# What each module-level name holds, when the source says: 'list', 'dict' or
# 'text'. Read by _static_kind, so that `for k in PRICES` walks keys and
# `for ch in NAME` walks characters instead of nothing.
_MODULE_KINDS = [{}]
# Parameters of the function being written that hold a list as JSON text --
# the selection of chips(multiple=True). `x in selected` asks the list.
_CUR_LIST_ARGS = [set()]

# get_value() of a component that lives on another screen. The same callback is
# written into every Activity, and where the field does not exist its empty
# value is the right answer, not a translation that failed -- so the guard
# against empty comparison sides must not refuse it. Ids of the parsed nodes,
# kept for one transpilation.
_ELSEWHERE_EMPTY = [set()]
# Constantes de modulo que so recebem numeros (VAT = 23). Viajam como
# String em Java, por isso a aritmetica tem de saber que sao numeros.
_NUMERIC_CONSTS = [{}]
# O mesmo, mas com o texto do literal, para sair como campo Java.
_NUMERIC_CONST_TEXT = [{}]
# Module-level names that a function rebinds after `global NAME`, as
# name -> (starting value as text, is_float or None for anything not a number).
# One value per process, like a module variable in Python: it lives in
# ApkpyReactiveState, beside the module lists the app appends to. Before, the
# function wrote `String COUNT = COUNT + 1;` and javac stopped the build.
_GLOBALS = [{}]
# Module-level names that only ever hold None, True or False (DEBUG = False):
# name -> "NONE" / "TRUE" / "FALSE". Each is a field pointing at ApkpyValues.
# Before, nothing declared them and the build died on cannot-find-symbol.
_SINGLETON_CONSTS = [{}]
# The name of a for over a list -> the Java Object holding the item as the
# JSON has it, while the body of that for is written and only when the body
# never changes the name. `for x in SCORES: out.append(x)` put '9', '12'
# in the copy as text, and `if x > best` compared them as text.
_RAW_LOOP_VARS = [{}]
# True while the body of a function that answers a value is written: a bare
# `return` there is `return ApkpyValues.NONE;`, not the `return;` javac refuses.
_RETURNS_VALUE = [False]
# Names the module imports (storage, https, clipboard, ...) and the names it
# gives a state(): their get()/keys()/copy() are the app's calls, not a dict's.
_IMPORTED_NAMES = [set()]
_STATE_NAMES = [set()]
# Every name the module gives a value to somewhere (assignment, parameter,
# for). requests.get(url) with requests never assigned is not a dict.
_BOUND_NAMES = [set()]
# Funcoes da app em que todos os return sao numeros: nome -> is_float. Sem
# isto, twice(n) + 1 colava os dois textos ("101" para n = 5).
_NUMERIC_RETURNS = [{}]
# What the app's own functions answer when every return says the same: name ->
# 'list', 'dict' or 'text' (_return_kinds). str(evens(xs)) showed the JSON,
# "[2,4]", and "te" in names() found the letters inside it.
_KIND_RETURNS = [{}]
# The parameters that every call of the module fills with a list or a dict:
# function -> {parameter: 'list' or 'dict'} (_param_kinds). `if xs:` read the
# JSON text "[]" as text that is not empty, so an empty list was true.
_PARAM_KINDS = [{}]
# The functions handed on as values (features/function_values.py).
_FN_TARGETS = [set()]
# Module lists written with numbers only that nothing changes or hands on:
# name -> 'int', 'float' or 'mixed' (_number_list_kind).
_FIXED_NUMBER_LISTS = [{}]
# Local names given a value that is surely a number, int or float as it turns
# out (a = sum(xs)): a + b glued two sums as text, 34 for 3 + 4. Kept by the
# function being written (_note_numberish), emptied at the start of each.
_NUMBERISH_NAMES = [set()]

# The Theme the module declared, so the night table can be built from it.
_APP_THEME = [None]

# The layouts of the sheets met while one screen's layout was written:
# {sheet name: xml}. Read by the caller right after _generate_layout_xml.
_SHEET_LAYOUTS = [{}]

# Where a relative icon path is resolved from.  The Previewer resolves against
# the app's .py file; without this the compiler resolved against the current
# working directory instead, so the same icon= could be found by one runtime
# and missing in the other depending on where the terminal happened to be.
_ASSET_BASE_DIR = [None]
# The typefaces this transpile declared, so _parse_typography_xml can map
# font-family onto a resource without threading the transpiler through.
_TRANSPILE_FONTS = [None]
