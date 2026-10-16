"""Human-readable diagnostics shared by ApkPy's Previewer and compiler.

The public application API deliberately does not depend on this module.  It is
small, has no GUI dependency and can therefore be used while importing a
``writehere.py`` file, from Tk callback handling, from the Android compiler and
from the Gradle build.

A diagnostic answers four questions in order: *where* it happened, *what*
happened, *why* it happened and *how* to fix it.  The "why" comes from the rule
catalogue below, which maps the messages ApkPy actually raises onto the reason
behind them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import difflib
import linecache
import os
import re
import sys
import traceback
from typing import Iterable, List, Optional, Pattern, Sequence, Tuple


DEBUG_ENV = "APKPY_DEBUG"
FRIENDLY_ERRORS_ENV = "APKPY_FRIENDLY_ERRORS"

DOCS_BASE = "https://repo-apkpy.pages.dev/"
_DOCS_ERRORS = DOCS_BASE + "friendly-errors/"


@dataclass(frozen=True)
class SourceLocation:
    path: str
    line: int = 0
    column: int = 0
    source: str = ""


@dataclass
class Diagnostic:
    code: str
    title: str
    message: str
    context: str = ""
    location: Optional[SourceLocation] = None
    cause: str = ""
    suggestions: List[str] = field(default_factory=list)
    expected: str = ""
    received: str = ""
    docs: str = ""
    technical: str = ""
    traceback_text: str = ""


class ApkpyError(Exception):
    """An ApkPy failure that already knows how to describe itself.

    Raise sites that can name the offending line of the *application* -- the
    Android compiler in particular, which reads ``writehere.py`` as text and so
    has no Python frame to point at -- attach it here instead of leaving
    :func:`diagnose_exception` to guess from the traceback.
    """

    def __init__(self, message, *, code="", title="", cause="", expected="",
                 received="", suggestions=(), docs="", line=0, column=0,
                 path=""):
        super().__init__(message)
        self.code = code
        self.title = title
        self.cause = cause
        self.expected = expected
        self.received = received
        self.suggestions = list(suggestions)
        self.docs = docs
        self.line = int(line or 0)
        self.column = int(column or 0)
        self.path = path


def debug_enabled() -> bool:
    return os.environ.get(DEBUG_ENV, "").strip().lower() in {
        "1", "true", "yes", "on",
    }


# --- Rule catalogue ---------------------------------------------------------
# Every entry matches a message ApkPy (or Python) actually produces.  The first
# matching rule decides the code, title, cause and expected value; ``{name}``
# placeholders are filled from the regular expression's named groups.

@dataclass(frozen=True)
class _Rule:
    pattern: Pattern
    code: str
    title: str
    cause: str = ""
    expected: str = ""
    suggestions: Tuple[str, ...] = ()
    docs: str = ""


def _rule(pattern, code, title, cause="", expected="", suggestions=(), docs=""):
    return _Rule(
        pattern=re.compile(pattern, re.IGNORECASE | re.DOTALL),
        code=code, title=title, cause=cause, expected=expected,
        suggestions=tuple(suggestions), docs=docs,
    )


_ANCHOR_COMPONENTS = _DOCS_ERRORS + "#u2001-components-and-arguments"
_ANCHOR_ICONS = DOCS_BASE + "reference/icons/"
_ANCHOR_DATA = DOCS_BASE + "data-core/"
_ANCHOR_NETWORK = _DOCS_ERRORS + "#n6001-network-and-urls"
_ANCHOR_JOBS = _DOCS_ERRORS + "#j7001-background-jobs"
_ANCHOR_COMPILER = _DOCS_ERRORS + "#c4001-android-compiler"
_ANCHOR_BUILD = _DOCS_ERRORS + "#b5001-android-build"
_ANCHOR_RUNTIME = _DOCS_ERRORS + "#p3001-previewer-runtime"


_RULES: Tuple[_Rule, ...] = (

    # -- U2xxx: components, layouts and their arguments ----------------------
    _rule(
        r"requires screen= or parent=|screen= or parent= in declarative apps",
        "U2001", "A component was created without a place to live",
        cause=(
            "A declarative app draws every component inside a Screen or a "
            "container. This call declares neither, so ApkPy has nowhere to "
            "attach it and Android would have no parent view to inflate it "
            "into."
        ),
        expected="screen=<your Screen> or parent=<row(...), column(...), card(...)>",
        suggestions=(
            "Add screen=home to place the component directly on a screen.",
            "Or add parent=my_row to place it inside a layout you already created.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"\(screen=\.\.\.\) expects an ApkPy Screen"
        r"|screen=\.\.\.\) requires a declared Screen"
        r"|observe\(screen=\.\.\.\) requires an ApkPy screen",
        "U2002", "screen= received something that is not a Screen",
        cause=(
            "screen= must receive the object returned by Screen(...). An id "
            "string, a component or None cannot be resolved to an Activity."
        ),
        expected="the Screen object itself, for example screen=home",
        suggestions=(
            "Create the screen first: home = Screen(id='home'), then pass screen=home.",
            "Pass the variable, not the id text: screen=home rather than screen='home'.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"expects an ApkPy component",
        "U2003", "This argument expects an ApkPy component",
        cause=(
            "The target has to be the object returned by a component factory "
            "such as label(), button() or image(). ApkPy binds to that "
            "object's generated Android view; a string id or a plain value has "
            "no view."
        ),
        expected="a component object, for example the value returned by label(...)",
        suggestions=(
            "Store the component in a variable and pass that variable.",
            "Check that the component is created before this line runs.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"expects an? (?P<expected_type>apkpy_lib\.\w+|[A-Z]\w+) instance",
        "U2014", "This argument expects a specific ApkPy object",
        cause=(
            "The value has to be the object produced by the matching ApkPy "
            "factory. ApkPy reads settings off that object while generating "
            "the Android project, so a dict, a string or a look-alike from "
            "another library carries nothing it can read."
        ),
        expected="a {expected_type} created by ApkPy",
        suggestions=(
            "Create the object with the ApkPy helper and pass that variable.",
            "Import it from apkpy_lib rather than building it by hand.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"job\.observe\(on_change=\.\.\.\)",
        "J7003", "job.observe() needs a callback that receives the status",
        cause=(
            "observe() delivers one status document on every WorkManager "
            "update, so it needs a function of one argument to receive it."
        ),
        expected="def queue_changed(status): ... passed as on_change=queue_changed",
        suggestions=(
            "Define a one-argument function and pass it without parentheses.",
        ),
        docs=_ANCHOR_JOBS,
    ),
    _rule(
        r"expects a callable|requires a function|needs a function"
        r"|requires a callback|expects a callback|needs a named function",
        "U2004", "A callback argument received a value instead of a function",
        cause=(
            "The function was called instead of being passed. Writing "
            "command=save() runs save immediately and hands ApkPy whatever it "
            "returned, which is usually None."
        ),
        expected="the function object itself, without parentheses",
        suggestions=(
            "Pass the function without calling it, for example command=save_note.",
            "Use a lambda when the callback needs arguments: command=lambda: save_note(3).",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"must be buttons|must be created with action\(|must use card_action\("
        r"|must be an icon name or action\(|expects row\(\.\.\.\) or column\("
        r"|must use row\(\.\.\.\) or column\(|Indexes must use db\.index\("
        r"|must be created with db\.|must use db\.asc\(\) or db\.desc\("
        r"|Data fields must use db\.",
        "U2005", "This argument only accepts a specific ApkPy factory",
        cause=(
            "These factories attach the metadata the Android generator needs "
            "(view type, styling, SQL type). A plain string, dict or foreign "
            "object carries none of it, so there would be nothing to translate."
        ),
        suggestions=(
            "Build the value with the factory named in the message.",
            "Keep the factory call inline so ApkPy can read it at build time.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"Use one of:\s*(?P<allowed>.+?)\s*$",
        "U2006", "A value is outside the accepted set",
        cause=(
            "This argument selects a fixed Android construct at build time, so "
            "only the listed values exist. An unlisted value has nothing to "
            "compile to."
        ),
        expected="one of: {allowed}",
        suggestions=("Use one of the listed values exactly, in lower case.",),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"must be one of\s*(?P<allowed>[^-]+?)\s*(?:-|$)",
        "U2006", "A value is outside the accepted set",
        cause=(
            "This argument selects a fixed Android construct at build time, so "
            "only the listed values exist."
        ),
        expected="one of {allowed}",
        suggestions=("Use one of the listed values exactly, in lower case.",),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"must be (?P<allowed>(?:\"[^\"]+\"|'[^']+'|[a-z_]+)"
        r"(?:\s*,\s*(?:\"[^\"]+\"|'[^']+'|[a-z_]+))*"
        r"(?:\s*,)?\s+or\s+(?:\"[^\"]+\"|'[^']+'|[a-z_]+))",
        "U2006", "A value is outside the accepted set",
        cause=(
            "This argument selects a fixed Android construct at build time, so "
            "only the listed values exist. An unlisted value has nothing to "
            "compile to."
        ),
        expected="{allowed}",
        suggestions=("Use one of the listed values exactly, in lower case.",),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"aspect_ratio",
        "U2009", "aspect_ratio was not understood",
        cause=(
            "aspect_ratio becomes a fixed width-to-height constraint in the "
            "generated layout, so it has to be a ratio ApkPy can divide."
        ),
        expected="a ratio such as '16:9' or '1:1', or a positive number such as 1.5",
        suggestions=("Use aspect_ratio='16:9' or aspect_ratio=1.5.",),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"must be between (?P<low>\S+) and (?P<high>\S+)",
        "U2007", "A number is outside the range this argument accepts",
        cause=(
            "The value is written into the generated Android code as a "
            "literal, so it has to be inside the range that construct "
            "supports."
        ),
        expected="a number from {low} to {high}",
        suggestions=(
            "Clamp the value before passing it, or pass a literal in range.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"must be a positive integer|must be greater than zero|must be an integer"
        r"|(?<!indices )must be integers|must be a non-negative number|must be a number"
        r"|cannot be negative|must be at least|must be at most",
        "U2007", "A numeric argument is the wrong kind of number",
        cause=(
            "ApkPy resolves this value to a pixel size, a column count or a "
            "row height while generating the layout, so it must be a concrete "
            "number of the right kind rather than text, None, or a float where "
            "an integer is required."
        ),
        expected="a whole number that satisfies the condition in the message",
        suggestions=(
            "Convert the value first, for example int(count) or max(1, count).",
            "Check that the value is not None before it reaches this call.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"must be a dict or JSON object|must be a dictionary|must be a dict\b"
        r"|must be a list\b|must be a string or a list|must be a string or dict"
        r"|must be a string\b|requires a literal fields dictionary",
        "U2008", "An argument has the wrong container type",
        cause=(
            "ApkPy reads this structure at build time to generate the Android "
            "views or the SQL. A value of another type cannot be walked, so "
            "the generator would produce nothing."
        ),
        expected="the container type named in the message",
        suggestions=(
            "Wrap a single value in the expected container, for example [value].",
            "Parse JSON text into a dict before passing it.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"All responsive arrangements must contain the same components",
        "U2010", "The responsive arrangements do not hold the same components",
        cause=(
            "responsive() generates one component set and several Android "
            "layout qualifiers over it. If the arrangements contain different "
            "components there is no single set to qualify."
        ),
        expected="the same components in every arrangement, ordered differently",
        suggestions=(
            "Keep the same component variables in mobile=, tablet= and desktop=.",
            "Change only the row/column arrangement between them.",
        ),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"icon file not found: (?P<name>.+)",
        "U2016", "That icon file does not exist",
        cause=(
            "icon= pointed at a file rather than a catalogue name, so ApkPy "
            "looked for it on disk relative to the folder your app lives in, "
            "and there was nothing there."
        ),
        expected="a path to an .svg file, relative to your app's folder",
        suggestions=(
            "Check the spelling and the folder, e.g. icon=\"assets/logo.svg\".",
            "Paths are relative to the .py file you run, not to where you "
            "opened the terminal.",
        ),
        docs=_ANCHOR_ICONS,
    ),
    _rule(
        r"icon file .* draws with strokes and no fill",
        "U2017", "That SVG is drawn with strokes, not filled shapes",
        cause=(
            "A stroke is a line with a thickness, not a shape. Android vector "
            "icons and the Previewer both fill shapes, so a stroked outline "
            "has no area to fill and would come out empty."
        ),
        expected="an SVG whose shapes are filled",
        suggestions=(
            "In Figma select the icon and use Outline stroke.",
            "In Illustrator use Object > Path > Outline Stroke.",
            "In Inkscape use Path > Stroke to Path.",
        ),
        docs=_ANCHOR_ICONS,
    ),
    _rule(
        r"icon file .* (?:uses <|has no filled shape)",
        "U2018", "ApkPy cannot convert this SVG to an icon",
        cause=(
            "An Android vector drawable only understands filled paths. Text, "
            "embedded images and re-used symbols have no equivalent, so "
            "converting them would silently produce the wrong icon."
        ),
        expected="an SVG built from filled paths, rectangles, circles or polygons",
        suggestions=(
            "Convert text to outlines before exporting.",
            "Flatten the artwork so every element is a real shape.",
            "If the icon embeds a photo, use image(src=...) instead -- icons "
            "are single-colour silhouettes.",
        ),
        docs=_ANCHOR_ICONS,
    ),
    _rule(
        r"icon file .* is not valid SVG"
        r"|icon path data (?:has an unexpected character|is missing arguments"
        r"|starts without a command)",
        "U2019", "That icon file is not readable as SVG",
        cause=(
            "ApkPy parses the SVG itself so the phone and the Previewer draw "
            "identical geometry. That means the file has to be well-formed XML "
            "with valid path data."
        ),
        expected="a valid .svg file",
        suggestions=(
            "Re-export the file from your design tool.",
            "Open it in a browser first -- if the browser cannot draw it, "
            "ApkPy cannot either.",
        ),
        docs=_ANCHOR_ICONS,
    ),
    _rule(
        r"requires a Material icon name",
        "U2011", "This icon name is not a Material icon",
        cause=(
            "Icons become Android vector drawables chosen by name at build "
            "time, so the name has to exist in the Material set ApkPy ships."
        ),
        expected="a Material icon name such as 'search', 'delete' or 'settings'",
        suggestions=(
            "Use a lower-case Material name with underscores, e.g. 'arrow_back'.",
        ),
        docs=_ANCHOR_ICONS,
    ),
    _rule(
        r"supports at most (?P<limit>\d+) nested levels|is too large"
        r"|exceeds max_length",
        "U2012", "A structural limit was exceeded",
        cause=(
            "ApkPy caps this structure so the generated Android code stays "
            "within the platform's own limits for view depth and payload size."
        ),
        suggestions=("Flatten or paginate the data before passing it.",),
        docs=_ANCHOR_COMPONENTS,
    ),
    _rule(
        r"require virtual_collection\(",
        "U2013", "This feed operation needs a virtual_collection()",
        cause=(
            "Feed mutations and pagination drive the RecyclerView adapter that "
            "virtual_collection() generates. Without one there is no adapter "
            "to update."
        ),
        expected="a component created with virtual_collection(...)",
        suggestions=(
            "Create the list with virtual_collection(...) and pass that component.",
        ),
        docs=DOCS_BASE + "production-feeds/",
    ),

    # -- J7xxx: background jobs ----------------------------------------------
    _rule(
        r"the function (?P<function>\w+)\(\) was not found in this file",
        "J7002", "The job's run function does not exist in this file",
        cause=(
            "background_job(run=...) names the function that becomes the body "
            "of the generated Worker. ApkPy looks it up by name in the same "
            "file; it cannot follow an import or a function defined inside "
            "another function."
        ),
        expected="a module-level def {function}(): in this file",
        suggestions=(
            "Define def {function}(): at the top level of the same file.",
            "Check the spelling against the name passed to run=.",
            "Move the function out of any class or enclosing function.",
        ),
        docs=_ANCHOR_JOBS,
    ),
    _rule(
        r"background_job\(",
        "J7001", "A background_job option is not one ApkPy can translate",
        cause=(
            "Job options map directly onto WorkManager constants "
            "(BackoffPolicy, ExistingWorkPolicy, NetworkType). A value outside "
            "the accepted set has no constant to map to."
        ),
        suggestions=(
            "Use retry='exponential' or retry='linear'.",
            "Use on_conflict='append', 'keep' or 'replace'.",
        ),
        docs=_ANCHOR_JOBS,
    ),

    # -- N6xxx: network and URLs ---------------------------------------------
    _rule(
        r"must use ws:// or wss://",
        "N6001", "The WebSocket URL is missing its scheme",
        cause=(
            "ApkPy chooses between a plain and a TLS socket from the scheme, "
            "so the URL has to start with ws:// or wss://."
        ),
        expected="wss://host/path for TLS, or ws://host/path for local development",
        suggestions=(
            "Prefix the address with wss:// -- Android blocks cleartext by default.",
        ),
        docs=_ANCHOR_NETWORK,
    ),
    _rule(
        r"must use http:// or https://|url must use http",
        "N6001", "The URL is missing its scheme",
        cause=(
            "The generated Android code passes this straight to the platform "
            "HTTP client, which rejects an address without a scheme."
        ),
        expected="a complete URL beginning with https://",
        suggestions=(
            "Use https:// in production -- Android blocks cleartext HTTP by default.",
            "Use http:// only for a local development server you have allowed.",
        ),
        docs=_ANCHOR_NETWORK,
    ),
    _rule(
        r"WebSocket (connection|handshake) closed|handshake rejected"
        r"|Invalid WebSocket handshake",
        "N6002", "The WebSocket connection did not survive the handshake",
        cause=(
            "The server closed the socket or answered something other than the "
            "101 upgrade the protocol requires. This is a server or network "
            "answer, not a mistake in the application code."
        ),
        suggestions=(
            "Confirm the URL, the port and that the server speaks WebSocket on that path.",
            "Check whether the server needs an auth token or an Origin header.",
        ),
        docs=DOCS_BASE + "guides/chat-realtime/",
    ),
    _rule(
        r"No route found",
        "N6004", "The routing service returned no route",
        cause=(
            "The routing provider answered successfully but found no path "
            "between the given points for this profile."
        ),
        suggestions=(
            "Check that both points are reachable by the chosen profile.",
            "Try profile='driving' before 'walking' or 'cycling'.",
        ),
        docs=DOCS_BASE + "guides/maps-tracking/",
    ),
    _rule(
        r"map points must be",
        "U2008", "A map point is not in a shape ApkPy understands",
        cause=(
            "Every point becomes a latitude/longitude pair in the generated "
            "map code, so it has to expose both values."
        ),
        expected="{'lat': 38.7, 'lng': -9.1} or [38.7, -9.1]",
        suggestions=(
            "Convert your records into dicts with 'lat' and 'lng' keys.",
        ),
        docs=DOCS_BASE + "guides/maps-tracking/",
    ),

    # -- C4xxx: Android compiler ---------------------------------------------
    _rule(
        r"db\.model\(\) declarations require one db\.schema\(\)",
        "C4003", "The models were declared without a schema",
        cause=(
            "The Android generator writes the database from the schema, not "
            "from the individual models. Without a db.schema() there is no "
            "version, no file name and no CREATE TABLE order to generate."
        ),
        expected="one db.schema(version=1, models=[...]) declaration",
        suggestions=(
            "Add db.schema(version=1, models=[...]) listing every model.",
        ),
        docs=_ANCHOR_DATA,
    ),

    _rule(
        r"db\.schema\(\w+=\[\.\.\.\]\) takes a db\.\w+\(\) call or the name of one",
        "C4004", "A schema list holds something ApkPy cannot read",
        cause=(
            "db.schema() builds the database from what its lists name: the "
            "models become tables, the relations become foreign keys and the "
            "migrations become ALTER TABLE. An entry that is neither a "
            "declaration nor the name of one has nothing to generate from, "
            "and ApkPy stops rather than leaving it out in silence -- which "
            "is what it used to do."
        ),
        expected="db.model(), db.relation() or db.migration() calls, or the names of some",
        suggestions=(
            "Write the declaration inline, or give it a name first and list "
            "the name.",
            "A list built at runtime cannot be read while compiling: name "
            "every declaration you want in the app.",
        ),
        docs=_ANCHOR_DATA,
    ),

    # -- D2xxx: Data Core ----------------------------------------------------
    _rule(
        r"Invalid (?P<kind>\w+) name .*use letters, digits and underscores",
        "D2001", "A Data Core name uses characters SQLite cannot accept",
        cause=(
            "Model, field, index and relation names become real SQL "
            "identifiers, so they are restricted to the characters an "
            "unquoted identifier may contain."
        ),
        expected="letters, digits and underscores, starting with a letter",
        suggestions=(
            "Replace spaces and dashes with underscores, e.g. 'note_items'.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"Unsupported data type|is not a db field declaration"
        r"|requires a db field declaration|received an invalid index"
        r"|contains a non-string field name",
        "D2009", "A field or index was not built with a db.* helper",
        cause=(
            "Data Core reads the SQL type, the constraints and the Android "
            "accessor from the declaration object. A bare Python value carries "
            "none of that, so there is nothing to turn into a column."
        ),
        expected="db.integer(), db.text(), db.real(), db.boolean(), db.datetime(), db.json(), db.blob() or db.index()",
        suggestions=(
            "Declare each field with a db.* factory inside the fields dictionary.",
            "Use db.index('name', fields=[...]) for indexes.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"migration operation|Invalid migration declaration"
        r"|requires a non-empty SQL statement",
        "D2010", "A migration step is not one Data Core can run",
        cause=(
            "Migrations are replayed on the device by generated Java, so each "
            "step has to be one of the operations that has a Java equivalent."
        ),
        expected="db.add_column(), db.drop_column(), db.rename_column(), db.add_index(), db.drop_index() or db.sql()",
        suggestions=(
            "Build every step with a db.* migration helper.",
            "Use db.sql('...') for anything the helpers do not cover.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"cannot be compared with nothing",
        "D2014", "A comparison was given nothing to compare against",
        cause=(
            "db.gt(), db.gte(), db.lt() and db.lte() ask which rows are above "
            "or below a value, and there is no answer to that when the value "
            "is missing. The two runtimes used to guess differently -- the "
            "Previewer returned nothing and Android returned the empty rows, "
            "which are the opposite rows -- so ApkPy now asks instead of "
            "guessing. A filter built from a form field nobody filled in "
            "lands here."
        ),
        expected="a value to compare against, or db.is_null() to ask for the empty rows",
        suggestions=(
            "Use db.is_null('field') to ask for the rows with no value.",
            "Leave the filter out when the value is missing: "
            "filters = [db.gt('score', floor)] if floor else [].",
            "db.eq() and db.ne() do accept None -- they ask whether the "
            "value is there at all.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"Unknown filter operation|requires at least one filter"
        r"|requires a text field",
        "D2011", "A query filter is not valid for this field",
        cause=(
            "Filters become SQL WHERE fragments, so the operation has to exist "
            "and has to suit the column's type. Text operations such as "
            "contains() have no meaning on a numeric column."
        ),
        expected="a db.eq(), db.gt(), db.contains() or similar filter over a compatible field",
        suggestions=(
            "Give db.and_() and db.or_() at least one inner filter.",
            "Use text filters only on db.text() columns.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"cannot be both required and optional"
        r"|min_value cannot be greater than max_value"
        r"|max_length cannot be negative",
        "D2012", "A field declares options that contradict each other",
        cause=(
            "These options become a single column definition plus its "
            "constraints. Two of them describe opposite rules, so no column "
            "could satisfy both."
        ),
        suggestions=(
            "Keep either required=True or optional=True, not both.",
            "Order the bounds so min_value is not above max_value.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"offset requires limit|limit and offset cannot be negative",
        "D2013", "The paging arguments are incomplete",
        cause=(
            "SQLite has no OFFSET without a LIMIT, so Data Core refuses the "
            "combination instead of inventing a page size."
        ),
        expected="limit=<page size> whenever offset= is used",
        suggestions=(
            "Pass limit= together with offset=, for example limit=20, offset=40.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"Index '(?P<index>[^']+)' does not exist",
        "D2005", "The index named in this migration does not exist",
        cause=(
            "The migration drops or renames an index the current schema does "
            "not declare, so there is nothing on the device to change."
        ),
        suggestions=(
            "Check the index name against db.index(...) in the model.",
            "Drop the index in the same migration that removed it from the model.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"Missing migration|migration path|is not consecutive"
        r"|without increasing its version|Downgrade .* is refused"
        r"|Two migrations start at version",
        "D2002", "The schema version and the migrations do not line up",
        cause=(
            "Data Core upgrades a real SQLite file, so it needs an unbroken "
            "chain of single-step migrations from the version on disk to the "
            "version declared in code. A gap would leave the database in a "
            "state no migration describes."
        ),
        expected="one db.migration() per version step, each advancing by exactly 1",
        suggestions=(
            "Raise the schema version by one and add the matching migration.",
            "Add the missing intermediate migrations rather than jumping versions.",
            "Delete the app data only if losing the existing rows is acceptable.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"destructive operations; pass destructive=True",
        "D2003", "This migration would drop data",
        cause=(
            "The migration removes a column, table or index. Data Core refuses "
            "silent data loss, so the intent has to be stated explicitly."
        ),
        expected="db.migration(..., destructive=True) once the loss is intended",
        suggestions=(
            "Add destructive=True if the data really should be removed.",
            "Copy the data into the new shape in an earlier migration first.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"Required field '(?P<field>[^']+)' is missing|cannot be null",
        "D2004", "A required column has no value",
        cause=(
            "The field was declared without optional=True and without a "
            "default, so SQLite's NOT NULL constraint rejects the row."
        ),
        expected="a value for every required field, or a declared default",
        suggestions=(
            "Include the field in the values dictionary.",
            "Declare it as optional=True, or give it default=... in the model.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"has no field\(s\)|Unknown field|Unknown filter field|Unknown order field"
        r"|references unknown field",
        "D2005", "A field name does not exist in this model",
        cause=(
            "Data Core validates every field name against the declared model "
            "before it builds SQL, so a typo is caught here instead of "
            "becoming a query that silently matches nothing."
        ),
        expected="a field name declared in db.model(...)",
        suggestions=(
            "Check the spelling against the fields dictionary of the model.",
            "Add the field to the model, plus a migration, if it is genuinely new.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"expects an integer|expects a real number|expects text|expects a boolean"
        r"|expects datetime or epoch|expects bytes|contains invalid JSON"
        r"|is not JSON serializable",
        "D2006", "A value does not match the column's declared type",
        cause=(
            "The column type becomes a real SQLite type and an Android "
            "accessor, so Data Core checks the value before writing it rather "
            "than storing something the generated Java cannot read back."
        ),
        expected="a value matching the type declared for this field",
        suggestions=(
            "Convert the value first, for example int(value) or str(value).",
            "Use db.text() for free-form values that are not numbers.",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"relation|foreign key|on_delete|parent_as|children_as|include accepts",
        "D2007", "A relation declaration or use is not valid",
        cause=(
            "Relations become foreign keys with real ON DELETE behaviour, so "
            "the parent key, the child key and their types have to agree "
            "before any SQL is generated."
        ),
        suggestions=(
            "Check that the foreign key exists on the child model and has the parent key's type.",
            "on_delete='set_null' needs the foreign key declared optional=True.",
            "Use one-level aliases in include=, such as include=['notes'].",
        ),
        docs=_ANCHOR_DATA,
    ),
    _rule(
        r"schema|primary key|auto_increment|database_name|Duplicate model"
        r"|Duplicate index|at least one field|more than one primary key",
        "D2008", "A schema or model declaration is not valid",
        cause=(
            "The schema is translated once into CREATE TABLE statements, so "
            "Data Core validates the whole declaration up front instead of "
            "failing later on the device."
        ),
        suggestions=(
            "Declare exactly one db.schema() containing every model.",
            "Give each model one primary key and at least one field.",
        ),
        docs=_ANCHOR_DATA,
    ),

    # -- P3xxx: runtime failures inside application code ----------------------
    _rule(
        r"'NoneType' object has no attribute '(?P<attribute>\w+)'",
        "P3002", "A component or value is None at this point",
        cause=(
            "The name exists but holds None, so .{attribute} has nothing to "
            "act on. In ApkPy this usually means the component was never "
            "assigned, a lookup returned nothing, or a function that should "
            "return a value ended without a return."
        ),
        expected="the object that should have been assigned earlier",
        suggestions=(
            "Check that the variable is assigned before this line runs.",
            "If it comes from a lookup, handle the empty case before using it.",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"invalid literal for int\(\) with base 10: (?P<value>.+)"
        r"|could not convert string to float: (?P<other>.+)",
        "P3011", "Text that is not a number was converted",
        cause=(
            "int() and float() accept only digits. Empty input fields, values "
            "read back from storage and values that crossed from Android all "
            "arrive as text, and an empty field is the usual reason this "
            "happens on the very first interaction."
        ),
        expected="text containing only digits",
        suggestions=(
            "Check the field is not empty before converting it.",
            "Use a default: int(value) if value.isdigit() else 0.",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"can only concatenate str",
        "E1401", "Text and a non-text value were joined",
        cause=(
            "Python does not convert automatically when joining with +. This "
            "is the most common Previewer callback failure, because progress "
            "values, counts and ids arrive as numbers."
        ),
        expected="every part of the expression as text",
        suggestions=(
            "Convert the non-text value first, for example 'Progress: ' + str(percent).",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"string indices must be integers",
        "P3005", "A string was used as if it were a record",
        cause=(
            "value['key'] was applied to text. In ApkPy this usually means a "
            "list of strings was passed where a list of records was expected."
        ),
        expected="a dictionary such as {'title': 'Example'}",
        suggestions=(
            "Pass records instead of strings, for example [{'title': name}].",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"unsupported operand type\(s\) for (?P<operator>\S+): "
        r"'(?P<left>[^']+)' and '(?P<right>[^']+)'",
        "P3006", "Two incompatible types were combined",
        cause=(
            "A {left} and a {right} cannot be combined with {operator}. Values "
            "that cross to Android arrive as text, so arithmetic on them needs "
            "an explicit conversion."
        ),
        suggestions=(
            "Convert first, for example int(status['pending']) + 1.",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"'(?P<value>\w+)' object is not callable",
        "P3007", "A value was used as if it were a function",
        cause=(
            "The name holds a {value} but is being called with (). A local "
            "variable shadowing a function is the usual reason."
        ),
        suggestions=(
            "Rename the variable so it stops hiding the function.",
            "Remove the parentheses if the value itself was intended.",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"takes (?P<takes>[\w ]+) positional arguments? but (?P<given>\d+)"
        r"|missing (?P<missing>\d+) required positional argument",
        "P3008", "A callback was called with a different number of arguments",
        cause=(
            "ApkPy calls each callback with a fixed signature. A status "
            "observer receives one argument; a button command receives none."
        ),
        expected="a function whose parameters match what ApkPy passes",
        suggestions=(
            "Match the signature shown in the API reference for this callback.",
            "Use a lambda to adapt it: command=lambda: save_note(note_id).",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"got an unexpected keyword argument '(?P<argument>\w+)'",
        "P3009", "This function has no argument called {argument}",
        cause=(
            "The argument name does not exist on this ApkPy function, so it "
            "would be silently ignored. ApkPy fails instead of generating an "
            "app that quietly lacks the setting."
        ),
        suggestions=(
            "Check the argument name against the API reference for this component.",
            "Confirm the installed ApkPy version supports this argument.",
        ),
        docs=DOCS_BASE + "api-reference/",
    ),
    _rule(
        r"division by zero",
        "P3010", "A division used zero as the divisor",
        cause=(
            "The divisor is zero, usually because a count or a total is still "
            "empty when the callback first runs."
        ),
        suggestions=(
            "Guard the division: percent = done * 100 // total if total else 0.",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
    _rule(
        r"list index out of range|string index out of range"
        r"|tuple index out of range",
        "P3004", "A list was read past its end",
        cause=(
            "The index is beyond the last element. An empty list is the usual "
            "reason, for example a query or a feed page that returned nothing."
        ),
        suggestions=(
            "Check the length before indexing, or iterate instead of indexing.",
            "Handle the empty case explicitly with an empty state.",
        ),
        docs=_ANCHOR_RUNTIME,
    ),
)


_KEY_ERROR_RULE = _rule(
    r".*",
    "P3003", "A key is missing from a record",
    cause=(
        "The dictionary does not contain this key. Records loaded from "
        "storage, a feed or a job payload only carry the keys that were "
        "written into them."
    ),
    expected="a record containing the key",
    suggestions=(
        "Use record.get('key', '') so a missing key becomes a default.",
        "Print the record to confirm the key names it really has.",
    ),
    docs=_ANCHOR_RUNTIME,
)


def _fill(template: str, match: Optional[re.Match]) -> str:
    if not template or match is None:
        return template
    values = {k: v for k, v in (match.groupdict() or {}).items() if v is not None}
    if not values:
        return template
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def _match_rule(message: str) -> Tuple[Optional[_Rule], Optional[re.Match]]:
    for rule in _RULES:
        found = rule.pattern.search(message)
        if found:
            return rule, found
    return None, None


# --- Location ---------------------------------------------------------------

def _display_path(path: str) -> str:
    if not path:
        return "writehere.py"
    absolute = os.path.abspath(path)
    try:
        relative = os.path.relpath(absolute, os.getcwd())
        if relative != ".." and not relative.startswith(".." + os.sep):
            return relative
    except (OSError, ValueError):
        pass
    return absolute


def _source_text(path: str, line: int, fallback: str = "") -> str:
    if fallback:
        return fallback.rstrip("\r\n")
    if not path or line <= 0:
        return ""
    return linecache.getline(path, line).rstrip("\r\n")


def _is_library_frame(filename: str) -> bool:
    normalized = str(filename).replace("\\", "/").lower()
    return "/apkpy_lib/" in normalized


def _line_from_source(source_code: Optional[str], line: int) -> str:
    if not source_code or line <= 0:
        return ""
    lines = source_code.splitlines()
    return lines[line - 1] if line <= len(lines) else ""


def _location_from_exception(error: BaseException, source_code: Optional[str],
                             filename: Optional[str]) -> Optional[SourceLocation]:
    # An ApkpyError that names an application line always wins: the compiler
    # reads writehere.py as text, so there is no Python frame to find.
    if isinstance(error, ApkpyError) and error.line > 0:
        path = error.path or str(filename or "writehere.py")
        source = (_line_from_source(source_code, error.line)
                  or _source_text(path, error.line))
        return SourceLocation(path, error.line, error.column, source)

    if isinstance(error, SyntaxError):
        syntax_path = str(error.filename or "")
        if syntax_path in {"", "<unknown>", "<string>"}:
            syntax_path = str(filename or "writehere.py")
        path = syntax_path
        line = int(error.lineno or 0)
        column = int(error.offset or 0)
        source = _source_text(path, line, str(error.text or ""))
        if not source:
            source = _line_from_source(source_code, line)
        return SourceLocation(path, line, column, source)

    frames = traceback.extract_tb(error.__traceback__) if error.__traceback__ else []
    application = os.path.basename(str(filename or "writehere.py")).lower()
    chosen = None
    # The application file is the most useful frame even when Tk or ApkPy later
    # catches the exception.  Otherwise prefer the last frame outside ApkPy.
    for frame in reversed(frames):
        base = os.path.basename(frame.filename).lower()
        if base in {application, "writehere.py"}:
            chosen = frame
            break
    if chosen is None:
        for frame in reversed(frames):
            if not _is_library_frame(frame.filename):
                chosen = frame
                break
    if chosen is None:
        # Everything happened inside ApkPy itself.  Pointing at library source
        # would send the reader to code they did not write, so report no
        # location and let the diagnostic carry the explanation instead.
        return None
    path = str(chosen.filename or filename or "writehere.py")
    return SourceLocation(
        path=path,
        line=int(chosen.lineno or 0),
        column=0,
        source=_source_text(path, int(chosen.lineno or 0), chosen.line or ""),
    )


# --- Suggestions and values -------------------------------------------------

def _public_apkpy_names() -> Sequence[str]:
    module = sys.modules.get("apkpy_lib")
    if module is None:
        return ()
    exported = getattr(module, "__all__", ())
    return tuple(str(name) for name in exported)


def _did_you_mean(name: str, candidates: Iterable[str]) -> Optional[str]:
    matches = difflib.get_close_matches(str(name), list(candidates), n=1, cutoff=0.55)
    return matches[0] if matches else None


_RECEIVED_PATTERNS = (
    re.compile(r"received\s+(?P<value>.+?)\s*$", re.IGNORECASE),
    re.compile(r"\breceived\b[:\s]+(?P<value>.+?)\s*$", re.IGNORECASE),
)


def _received_from_error(error: BaseException, message: str) -> str:
    if isinstance(error, ApkpyError) and error.received:
        return error.received
    if isinstance(error, KeyError) and error.args:
        return repr(error.args[0])
    if isinstance(error, AttributeError):
        found = re.search(r"'(?P<owner>[\w.]+)' object has no attribute", message)
        if found:
            return "an object of type %s" % found.group("owner")
    for pattern in _RECEIVED_PATTERNS:
        found = pattern.search(message)
        if found:
            return found.group("value")
    return ""


def _argument_hint(message: str) -> str:
    """Name the call to look for when the message embeds ``factory(arg=...)``."""
    found = re.search(r"\b(?P<call>[a-z_]{3,})\(\s*(?P<argument>[a-z_]+)\s*=", message)
    if not found:
        return ""
    return "Look for %s(... %s=... ) in your application." % (
        found.group("call"), found.group("argument"),
    )


def _message_suggestions(message: str) -> List[str]:
    """Corrective actions for a message, without building a full diagnostic."""
    rule, match = _match_rule(message)
    if rule is None:
        return []
    return [_fill(item, match) for item in rule.suggestions]


# --- Diagnosis --------------------------------------------------------------

_FALLBACKS = {
    "SyntaxError": ("E1001", "Python could not read this code"),
    "ModuleNotFoundError": ("E1101", "A required Python module is not installed"),
    "ImportError": ("E1102", "This import is not available"),
    "NameError": ("E1201", "A name is used before it exists"),
    "FileNotFoundError": ("E1301", "ApkPy could not find a required file"),
    "TypeError": ("E1401", "A value has the wrong type"),
    "ValueError": ("E1402", "A value is not valid for this ApkPy operation"),
}


def diagnose_exception(error: BaseException, *, context: str = "",
                       source_code: Optional[str] = None,
                       filename: Optional[str] = None,
                       traceback_object=None) -> Diagnostic:
    raw = str(error) or error.__class__.__name__
    error_name = error.__class__.__name__
    location = _location_from_exception(error, source_code, filename)

    if isinstance(error, KeyError):
        rule, match = _KEY_ERROR_RULE, _KEY_ERROR_RULE.pattern.search(raw)
    else:
        rule, match = _match_rule(raw)

    code = title = cause = expected = docs = ""
    suggestions: List[str] = []
    if rule is not None:
        code, title = rule.code, _fill(rule.title, match)
        cause = _fill(rule.cause, match)
        expected = _fill(rule.expected, match)
        docs = rule.docs
        suggestions = [_fill(item, match) for item in rule.suggestions]

    received = _received_from_error(error, raw)
    if not received and match is not None:
        # A rule that captured the offending value names it "value"/"received".
        groups = match.groupdict() or {}
        received = str(groups.get("received") or groups.get("value") or "")

    # A structured ApkpyError always overrides the catalogue.
    if isinstance(error, ApkpyError):
        code = error.code or code
        title = error.title or title
        cause = error.cause or cause
        expected = error.expected or expected
        docs = error.docs or docs
        if error.suggestions:
            suggestions = list(error.suggestions) + suggestions

    if isinstance(error, SyntaxError):
        code, title = "E1001", "Python could not read this code"
        cause = cause or (
            "Python parses the whole file before ApkPy sees any of it, so one "
            "unbalanced line stops the application before it starts."
        )
        lowered = raw.lower()
        if "expected ':'" in lowered:
            suggestions.insert(0, "Add : at the end of the function, if, for, while or class line.")
        elif "was never closed" in lowered or "unexpected eof" in lowered:
            suggestions.insert(0, "Close the missing parenthesis, bracket, brace or quoted string.")
        else:
            suggestions.insert(0, "Check the highlighted line and the line immediately above it.")
        docs = docs or _DOCS_ERRORS
    elif isinstance(error, ModuleNotFoundError):
        code, title = "E1101", "A required Python module is not installed"
        received = received or str(getattr(error, "name", None) or raw)
        cause = cause or (
            "The import is valid Python, but the package is not present in the "
            "interpreter running this file. Several interpreters on one "
            "machine is the usual reason."
        )
        suggestions.append("Install the missing package in the same Python environment that runs ApkPy.")
        suggestions.append("Run python -m pip show apkpy to confirm which environment is active.")
        docs = docs or _DOCS_ERRORS
    elif isinstance(error, ImportError):
        code, title = "E1102", "This import is not available"
        cause = cause or (
            "ApkPy exports a fixed set of public names. This one is either "
            "misspelled or belongs to a different ApkPy version."
        )
        found = re.search(r"cannot import name ['\"]([^'\"]+)", raw)
        if found:
            missing = found.group(1)
            received = received or missing
            close = _did_you_mean(missing, _public_apkpy_names())
            if close:
                suggestions.insert(0, "Did you mean: from apkpy_lib import %s" % close)
        suggestions.append("Check the Essential API reference or upgrade ApkPy in this environment.")
        docs = docs or DOCS_BASE + "reference/essential/"
    elif isinstance(error, NameError):
        code, title = "E1201", "A name is used before it exists"
        cause = cause or (
            "Python runs the file from top to bottom, so a component or "
            "function used above the line that creates it does not exist yet."
        )
        found = re.search(r"name ['\"]([^'\"]+)['\"] is not defined", raw)
        if found:
            missing = found.group(1)
            received = received or missing
            close = _did_you_mean(missing, _public_apkpy_names())
            if close:
                suggestions.insert(0, "Did you mean '%s'?" % close)
        suggestions.append("Define or import this name before the highlighted line.")
        docs = docs or _DOCS_ERRORS
    elif error_name == "DataCoreError":
        code = code if code.startswith("D2") else "D2001"
        title = title or "Data Core rejected this declaration or operation"
        cause = cause or (
            "Data Core validates declarations and values before they reach "
            "SQLite, so the problem surfaces here instead of as a corrupt "
            "database on the device."
        )
        docs = docs or _ANCHOR_DATA
        if not suggestions:
            suggestions.append("Check the model fields, filters, relation and schema version used by this operation.")
    elif isinstance(error, FileNotFoundError):
        code, title = "E1301", "ApkPy could not find a required file"
        received = received or str(getattr(error, "filename", "") or raw)
        cause = cause or (
            "The path is resolved relative to the folder the command was run "
            "from, not relative to the file that names it."
        )
        suggestions.append("Check that the path exists and is relative to the folder containing writehere.py.")
        docs = docs or _DOCS_ERRORS

    if not code:
        lowered_context = context.lower()
        if "compiler" in lowered_context or "build" in lowered_context:
            code, title = "C4001", "The Android compiler could not translate this code"
            cause = cause or (
                "The compiler generates Java from a supported subset of "
                "Python. This construct has no equivalent it can emit."
            )
            docs = docs or _ANCHOR_COMPILER
            suggestions.append("Use an ApkPy-supported API or simplify the highlighted expression.")
        elif "callback" in lowered_context or "preview" in lowered_context or "job" in lowered_context:
            code, title = "P3001", "A Previewer callback failed"
            cause = cause or (
                "The failure happened inside application code that ApkPy "
                "called in response to an interaction."
            )
            docs = docs or _ANCHOR_RUNTIME
            suggestions.append("Inspect the callback shown under Where and validate the values it receives.")
        else:
            fallback = _FALLBACKS.get(error_name)
            if fallback:
                code, title = fallback
            else:
                code, title = "E1999", "The application stopped because of an unexpected error"
            suggestions.append("Check the highlighted application line. Run again with APKPY_DEBUG=1 for the full traceback.")

    if not title:
        fallback_code, title = _FALLBACKS.get(
            error_name, (code, "ApkPy stopped this operation"),
        )
        code = code or fallback_code

    hint = _argument_hint(raw)
    if hint and hint not in suggestions:
        suggestions.append(hint)

    tb = traceback_object if traceback_object is not None else error.__traceback__
    traceback_text = "".join(traceback.format_exception(type(error), error, tb))
    return Diagnostic(
        code=code,
        title=title,
        message=raw,
        context=context,
        location=location,
        cause=cause,
        suggestions=list(dict.fromkeys(suggestions)),
        expected=expected,
        received=received,
        docs=docs,
        technical="%s: %s" % (error_name, raw),
        traceback_text=traceback_text,
    )


# --- Android build failures -------------------------------------------------
# Gradle prints a wall of output and ends with "BUILD FAILED".  These rules turn
# the signatures ApkPy can recognise into the same diagnostic format.

@dataclass(frozen=True)
class _BuildRule:
    pattern: Pattern
    code: str
    title: str
    cause: str
    suggestions: Tuple[str, ...]
    expected: str = ""


def _build_rule(pattern, code, title, cause, suggestions, expected=""):
    return _BuildRule(
        re.compile(pattern, re.IGNORECASE | re.MULTILINE), code, title, cause,
        tuple(suggestions), expected,
    )


_BUILD_RULES: Tuple[_BuildRule, ...] = (
    _build_rule(
        r"Unsupported class file major version (?P<version>\d+)"
        r"|Unsupported Java\.? (?P<java>\d+)"
        r"|requires Java (?P<required>\d+)"
        r"|Android Gradle plugin requires Java"
        r"|invalid source release",
        "B5002", "Gradle ran on a Java version it does not support",
        cause=(
            "Gradle and the Android Gradle Plugin only accept a range of JDKs. "
            "A newer system Java was picked up before the managed one, and the "
            "class files it produces are rejected."
        ),
        suggestions=(
            "Run `apkpy setup` to install and select a supported JDK (17-21).",
            "Run `apkpy doctor` to see which JDK the build is actually using.",
            "Check that JAVA_HOME in this shell does not point at a newer JDK.",
        ),
        expected="JDK 17 to 21",
    ),
    _build_rule(
        r"You have not accepted the license|SDK license"
        r"|licen[cs]es have not been accepted"
        r"|Failed to install the following Android SDK packages",
        "B5003", "The Android SDK is incomplete or its licences are not accepted",
        cause=(
            "Gradle downloads platform and build-tools packages on demand and "
            "cannot install them until the SDK licences have been accepted."
        ),
        suggestions=(
            "Run `apkpy setup` to install the SDK packages and accept the licences.",
            "Run `apkpy doctor` afterwards to confirm the SDK is complete.",
        ),
    ),
    _build_rule(
        r"AAPT: error|resource (?P<resource>\S+) not found"
        r"|failed linking references|Android resource linking failed"
        r"|error: resource",
        "B5004", "Android could not link the generated resources",
        cause=(
            "A layout, drawable or style referenced by the generated project "
            "is missing or malformed. After changing the app this usually "
            "means the project folder still holds files from an earlier "
            "generation."
        ),
        suggestions=(
            "Delete the generated project folder and build again so every file is rewritten.",
            "Check that every image path used in writehere.py exists.",
            "Read the AAPT line under Received: it names the exact resource.",
        ),
    ),
    _build_rule(
        r"^(?P<file>\S+\.java):(?P<line>\d+): error: (?P<detail>.+)$"
        r"|Execution failed for task ':app:compile\w*JavaWithJavac'"
        r"|error: cannot find symbol",
        "B5005", "The generated Java did not compile",
        cause=(
            "ApkPy produced Java that javac rejected. This is an ApkPy defect "
            "rather than a mistake in the application: a construct was "
            "translated into Java that does not compile."
        ),
        suggestions=(
            "Note the .java file and line under Received; the generated sources stay on disk.",
            "Remove the most recently added construct to identify which one it is.",
            "Report the smallest writehere.py that reproduces it, with this diagnostic.",
        ),
    ),
    _build_rule(
        r"Could not (?:reserve|allocate) enough space|OutOfMemoryError"
        r"|Java heap space|Gradle build daemon disappeared",
        "B5006", "Gradle ran out of memory or its daemon died",
        cause=(
            "The Gradle worker exhausted the heap it was given, or was killed "
            "by the operating system while compiling."
        ),
        suggestions=(
            "Close other heavy applications and run the build again.",
            "Raise the heap in the project's gradle.properties, e.g. org.gradle.jvmargs=-Xmx2g.",
        ),
    ),
    _build_rule(
        r"Could not resolve|Could not download|Connection (?:timed out|refused)"
        r"|Could not GET|Network is unreachable",
        "B5007", "Gradle could not download a dependency",
        cause=(
            "The first build fetches Gradle plugins and AndroidX libraries "
            "from the network. A proxy, a firewall or an offline machine stops "
            "it."
        ),
        suggestions=(
            "Check the connection and build again; the downloads are cached afterwards.",
            "Configure the proxy in gradle.properties if this machine needs one.",
        ),
    ),
    _build_rule(
        r"INSTALL_FAILED|device (?:not found|offline|unauthorized)"
        r"|no devices/emulators found",
        "B5008", "The APK was built but could not be installed on the device",
        cause=(
            "adb reached the build output but the device refused the install. "
            "An unauthorised device, a conflict with an already installed "
            "copy, or a different signing key are the usual reasons."
        ),
        suggestions=(
            "Accept the USB debugging prompt on the device, then run the command again.",
            "Uninstall the previous version if it was signed with a different key.",
        ),
    ),
)


_BUILD_DETAIL = re.compile(
    r"^(?:e:|error|FAILURE|Caused by|\*\s*What went wrong|>\s)|error:",
    re.IGNORECASE,
)

# Lines that name a file, a position and a reason: the ones a reader actually
# needs.  Gradle prints them before its own summary, so they must be selected
# rather than reached by tailing the output.
_BUILD_PRECISE = re.compile(
    r"\.java:\d+:\s*error:|^e:\s|AAPT:\s*error:|error: resource\b"
    r"|error: cannot find symbol|Unsupported class file major version"
    r"|^\s*symbol:|^\s*location:",
    re.IGNORECASE,
)

# Gradle's closing advice repeats on every failure and carries no information.
_BUILD_NOISE = re.compile(
    r"Run with --(?:info|scan|stacktrace|debug)|Get more help at|^\* Try:$"
    r"|BUILD FAILED in|actionable tasks?:",
    re.IGNORECASE,
)


def _build_detail_lines(text):
    """The most informative lines of a Gradle failure, most precise first."""
    precise, general = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _BUILD_NOISE.search(line):
            continue
        if _BUILD_PRECISE.search(line):
            if line not in precise:
                precise.append(line)
        elif _BUILD_DETAIL.search(line):
            if line not in general:
                general.append(line)
    return precise[:6] + general[-4:] if precise else general[-6:]


def diagnose_build_failure(output: str, *, task: str = "",
                           project_dir: str = "",
                           context: str = "Android APK build") -> Diagnostic:
    """Turn captured Gradle output into a diagnostic.

    ``output`` is the combined stdout/stderr of the Gradle run.  When no rule
    matches, the diagnostic still names the task, the generated project and the
    last meaningful lines, so the reader is never left with "see the output
    above".
    """
    text = output or ""
    matched = None
    match = None
    for rule in _BUILD_RULES:
        found = rule.pattern.search(text)
        if found:
            matched, match = rule, found
            break

    detail_lines = _build_detail_lines(text)
    received = "\n  ".join(detail_lines) if detail_lines else ""
    technical = ("Gradle task: %s" % task) if task else "Gradle build"

    if matched is None:
        suggestions = [
            "Read the lines under Received: they carry Gradle's own reason.",
            "Run `apkpy doctor` to rule out a toolchain problem.",
            "Re-run the same Gradle task inside the generated project for the full report.",
        ]
        if project_dir:
            suggestions.append("Generated project: %s" % project_dir)
        return Diagnostic(
            code="B5009",
            title="The Gradle build failed",
            message="Gradle stopped before producing an artifact.",
            context=context,
            cause=(
                "ApkPy generated the Android project successfully, so the "
                "failure happened while Gradle compiled or packaged it. The "
                "signature is not one ApkPy recognises yet."
            ),
            received=received,
            suggestions=suggestions,
            docs=_ANCHOR_BUILD,
            technical=technical,
        )

    # The line that identified the failure is the one worth reading, and it
    # does not always look like an "error:" line, so it is pinned to the front.
    signature = text[match.start():match.end()].strip().splitlines()
    if signature and signature[0] not in detail_lines:
        received = "\n  ".join([signature[0]] + detail_lines[:5])

    suggestions = [_fill(item, match) for item in matched.suggestions]
    if project_dir:
        suggestions.append("Generated project: %s" % project_dir)
    return Diagnostic(
        code=matched.code,
        title=matched.title,
        message=_fill(matched.title, match),
        context=context,
        cause=_fill(matched.cause, match),
        expected=_fill(matched.expected, match),
        received=received,
        suggestions=suggestions,
        docs=_ANCHOR_BUILD,
        technical=technical,
    )


# --- Rendering --------------------------------------------------------------

# Windows consoles with a legacy code page replace these with a broken glyph,
# so they are normalised before anything is printed.
_ASCII_REPLACEMENTS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "·": "-",
    "→": "->", "←": "<-", "≤": "<=", "≥": ">=",
    " ": " ", "•": "-",
}


def _ascii_safe(text: str) -> str:
    for source, target in _ASCII_REPLACEMENTS.items():
        if source in text:
            text = text.replace(source, target)
    return text


def _wrap(text: str, width: int = 74, indent: str = "  ") -> List[str]:
    """Wrap one paragraph so long explanations stay readable in a terminal."""
    words = str(text).split()
    if not words:
        return []
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(indent + current)
            current = word
    lines.append(indent + current)
    return lines


def render_diagnostic(diagnostic: Diagnostic, *,
                      include_traceback: Optional[bool] = None) -> str:
    # Keep the header ASCII-only so Windows terminals with legacy encodings do
    # not replace the separator with a broken glyph.
    lines = ["", "APKPY %s - %s" % (diagnostic.code, diagnostic.title)]
    if diagnostic.context:
        lines.extend(["", "Context:", "  " + diagnostic.context])
    if diagnostic.location:
        location = diagnostic.location
        place = _display_path(location.path)
        if location.line:
            place += ":%s" % location.line
            if location.column:
                place += ":%s" % location.column
        lines.extend(["", "Where:", "  " + place])
        if location.source:
            lines.append("  " + location.source.strip())
            if location.column > 0:
                lines.append("  " + (" " * max(0, location.column - 1)) + "^")
    lines.extend(["", "What happened:"])
    lines.extend(_wrap(diagnostic.message) or ["  " + diagnostic.message])
    if diagnostic.cause:
        lines.extend(["", "Why this happened:"])
        lines.extend(_wrap(diagnostic.cause))
    if diagnostic.received:
        lines.extend(["", "Received:", "  " + diagnostic.received])
    if diagnostic.expected:
        lines.extend(["", "Expected:", "  " + diagnostic.expected])
    if diagnostic.suggestions:
        lines.extend(["", "How to fix:"])
        for index, suggestion in enumerate(diagnostic.suggestions, 1):
            wrapped = _wrap(suggestion, width=70, indent="     ")
            if wrapped:
                lines.append("  %s. %s" % (index, wrapped[0].strip()))
                lines.extend(wrapped[1:])
    if diagnostic.docs:
        lines.extend(["", "Read more:", "  " + diagnostic.docs])
    if diagnostic.technical:
        # Only when there is something to show.  Diagnostics built by hand --
        # C4002 and U2015 -- carry no exception text, and an empty heading
        # reads like the report was truncated.
        lines.extend(["", "Technical details:", "  " + diagnostic.technical])
    show_traceback = debug_enabled() if include_traceback is None else include_traceback
    if show_traceback and diagnostic.traceback_text:
        lines.extend(["", "Full traceback (APKPY_DEBUG=1):",
                      diagnostic.traceback_text.rstrip()])
    elif diagnostic.traceback_text:
        lines.extend(["", "Need the full traceback? Run again with APKPY_DEBUG=1."])
    return _ascii_safe("\n".join(lines).rstrip() + "\n")


def format_exception(error: BaseException, *, context: str = "",
                     source_code: Optional[str] = None,
                     filename: Optional[str] = None,
                     traceback_object=None,
                     include_traceback: Optional[bool] = None) -> str:
    return render_diagnostic(
        diagnose_exception(
            error,
            context=context,
            source_code=source_code,
            filename=filename,
            traceback_object=traceback_object,
        ),
        include_traceback=include_traceback,
    )


def _write(text: str, stream) -> None:
    target = stream or sys.stderr
    try:
        print(text, file=target, end="")
    except UnicodeEncodeError:
        encoding = getattr(target, "encoding", None) or "ascii"
        print(text.encode(encoding, "backslashreplace").decode(encoding),
              file=target, end="")


def report_exception(error: BaseException, *, context: str = "",
                     traceback_object=None, stream=None,
                     source_code: Optional[str] = None,
                     filename: Optional[str] = None) -> str:
    rendered = format_exception(
        error, context=context, traceback_object=traceback_object,
        source_code=source_code, filename=filename,
    )
    _write(rendered, stream)
    return rendered


def report_diagnostic(diagnostic: Diagnostic, *, stream=None) -> str:
    rendered = render_diagnostic(diagnostic)
    _write(rendered, stream)
    return rendered


def install_exception_hook() -> None:
    """Format uncaught application errors after ``apkpy_lib`` is imported."""
    if os.environ.get(FRIENDLY_ERRORS_ENV, "1").strip().lower() in {"0", "false", "off"}:
        return
    if getattr(sys.excepthook, "_apkpy_friendly_hook", False):
        return
    original = sys.excepthook

    def apkpy_exception_hook(error_type, error, tb):
        if issubclass(error_type, KeyboardInterrupt):
            original(error_type, error, tb)
            return
        report_exception(error, context="Application startup", traceback_object=tb)

    apkpy_exception_hook._apkpy_friendly_hook = True
    apkpy_exception_hook._apkpy_original_hook = original
    sys.excepthook = apkpy_exception_hook


def install_tk_exception_hook(root) -> None:
    """Replace Tkinter's raw callback traceback with the same ApkPy format."""
    def report_callback_exception(error_type, error, tb):
        report_exception(error, context="Previewer callback", traceback_object=tb)

    root.report_callback_exception = report_callback_exception
