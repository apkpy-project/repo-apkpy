"""
Configuração da app via `apkpy.toml` — nome, package id (Play Store), versão e
ícone. Lido pelo CLI no `apkpy run` / `apkpy build`. NÃO toca no transpilador:
os valores são aplicados ao projeto Gradle/Manifest gerado (pós-processamento).

Exemplo de apkpy.toml:

    [app]
    name = "Minha App"
    application_id = "com.exemplo.minhaapp"
    version_name = "1.0"
    version_code = 1
    icon = "icon.png"
"""
import os
import re

try:                       # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as _toml          # backport para 3.8–3.10
    except ModuleNotFoundError:
        _toml = None

CONFIG_FILENAME = "apkpy.toml"

# package Java interno (namespace) — NÃO muda; só o applicationId (id da loja) é
# que o utilizador personaliza. Os dois podem divergir no Android.
INTERNAL_NAMESPACE = "com.apkpy.app"
DEFAULT_APPLICATION_ID = "com.apkpy.app"

# The Android an app is built against and says it was made for. Google Play
# takes new apps and updates only at the newest level but one: API 36
# (Android 16) since 31 August 2026. One number, read by the Gradle files, by
# the Studio's project writer and by `apkpy setup` -- they said 35, 34 and 35.
MIN_SDK = 24
TARGET_SDK = 36
COMPILE_SDK = 36

# id de applicationId válido: 2+ segmentos separados por '.', cada um a começar
# por letra (regra do Android/Java para package names).
_APP_ID_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$')


def default_config(project_dir="."):
    """Config por omissão — usada quando não há apkpy.toml."""
    folder = os.path.basename(os.path.abspath(project_dir)) or "ApkPy App"
    return {
        "name": folder,
        "application_id": DEFAULT_APPLICATION_ID,
        "version_name": "1.0",
        "version_code": 1,
        "icon": None,
    }


def load_config(project_dir="."):
    """Lê apkpy.toml de project_dir e devolve um dict completo (com defaults
    preenchidos). Se o ficheiro não existir, devolve os defaults. Valores
    inválidos são corrigidos para o default, com um aviso em warnings[]."""
    cfg = default_config(project_dir)
    cfg["_warnings"] = []
    path = os.path.join(project_dir, CONFIG_FILENAME)
    if not os.path.exists(path):
        cfg["_found"] = False
        return cfg
    cfg["_found"] = True

    if _toml is None:
        cfg["_warnings"].append(
            "apkpy.toml found but 'tomli' is missing (pip install tomli) — ignoring it."
        )
        return cfg

    try:
        with open(path, "rb") as f:
            data = _toml.load(f)
    except Exception as e:
        cfg["_warnings"].append(f"apkpy.toml is invalid ({e}) — using defaults.")
        return cfg

    app = data.get("app", data) if isinstance(data, dict) else {}

    if isinstance(app.get("name"), str) and app["name"].strip():
        cfg["name"] = app["name"].strip()

    app_id = app.get("application_id")
    if isinstance(app_id, str) and app_id.strip():
        if _APP_ID_RE.match(app_id.strip()):
            cfg["application_id"] = app_id.strip()
        else:
            cfg["_warnings"].append(
                f"invalid application_id: '{app_id}' — use something like "
                f"'com.example.app' (2+ segments). Keeping '{cfg['application_id']}'."
            )

    if isinstance(app.get("version_name"), (str, int, float)):
        cfg["version_name"] = str(app["version_name"]).strip()

    vc = app.get("version_code")
    if isinstance(vc, int) and vc > 0:
        cfg["version_code"] = vc
    elif vc is not None:
        cfg["_warnings"].append(
            f"version_code must be an integer > 0 (was {vc!r}) — using {cfg['version_code']}."
        )

    icon = app.get("icon")
    if isinstance(icon, str) and icon.strip():
        icon_path = icon.strip()
        if not os.path.isabs(icon_path):
            icon_path = os.path.join(project_dir, icon_path)
        if os.path.exists(icon_path):
            cfg["icon"] = icon_path
        else:
            cfg["_warnings"].append(f"icon not found: {icon} — the app will keep the default icon.")

    return cfg


_TEMPLATE = '''\
# Your ApkPy app configuration.
# These values are applied at build time (apkpy run / apkpy build).

[app]
# The name shown under the icon on the phone.
name = "{name}"

# Unique Play Store identifier (do NOT change it after publishing).
# Format: reversed domain + name, e.g. "com.mycompany.myapp".
application_id = "com.example.{slug}"

# The user-visible version, and the internal code (bump by 1 on each release).
version_name = "1.0"
version_code = 1

# (Optional) App icon — a square PNG (ideally 512x512).
# Uncomment and point it to your file (needs Pillow: pip install Pillow):
# icon = "icon.png"
'''


def scaffold_text(project_dir=".", name=None):
    """Conteúdo de um apkpy.toml inicial. Usa `name` se for dado; senão, o nome
    da pasta. O slug do application_id é derivado do nome."""
    folder = name or os.path.basename(os.path.abspath(project_dir)) or "my_app"
    slug = re.sub(r'[^a-z0-9]+', '', folder.lower()) or "myapp"
    return _TEMPLATE.format(name=folder, slug=slug)


def write_scaffold(project_dir=".", name=None):
    """Escreve um apkpy.toml novo em project_dir (com o `name` dado, se houver).
    Devolve o caminho do ficheiro."""
    path = os.path.join(project_dir, CONFIG_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write(scaffold_text(project_dir, name=name))
    return path
