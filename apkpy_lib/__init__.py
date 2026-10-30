"""Public ApkPy API.

Normal applications receive the complete declarative API and the desktop
Previewer. Compiler hosts such as ApkPy Studio set ``APKPY_HEADLESS_CORE=1``
before importing ``apkpy_lib.core`` so Android never attempts to load Tkinter.
"""

import os as _os


_HEADLESS_CORE = _os.environ.get("APKPY_HEADLESS_CORE", "").strip() == "1"

# python writehere.py: watch the folder and run the app in a second Python,
# so that a save reloads the Previewer. This comes before Tk is imported, so
# the watching Python opens no window. See apkpy_lib/reload.py.
from . import reload as _reload
_reload.start()

if not _HEADLESS_CORE:
    from .ui import (
        Screen, ReactiveState, state, lifecycle, bottom_nav, BottomNav, mini_player, app_bar, sliver_app_bar, action, on_click_navigate, back, button, label, inputs, input_field, validate, image, view_image, video, avatar, container, card, card_action, drawer, DrawerDef, font, row, column, responsive, list_row, list_view, virtual_collection, swipe, SwipeAction, pager, tab, PagerDef, chart, ChartDef, chips, segmented, ChoiceDef, carousel, grid, spinner, skeleton, empty_state, error_state, OverlayDef, bottom_sheet, modal, menu, popup_menu, context_menu, snackbar, tooltip, date_picker, time_picker, run, toast, notify, share,
        declare_permissions, permissions, PermissionsAPI, storage, StorageAPI, appearance, AppearanceAPI, translations, t, language, LanguageAPI, crash, CrashAPI, app, AppAPI, crypto, CryptoAPI, db, SQLiteAPI, https, HttpsAPI, json_get,
        service, ServiceAPI, clipboard, ClipboardAPI, camera, CameraAPI, gallery, GalleryAPI,
        location, LocationAPI, alert, confirm, device, random, RandomAPI, datetime, DatetimeAPI, audio, AudioAPI, files, FilesAPI, uploads, UploadsAPI,
        auth, AuthAPI, apps, AppsAPI, secure_screen
    )
    from .theme import Theme
    from .websocket import WebSocketAPI, websocket
    from .features.push import PushAPI, push
    from .features.notifications import NotificationsAPI, notifications
    from .features.rich_content import markdown, rich_text, tree_view
    from .features.jobs import JobDef, JobStatus, background_job
    from .features.file_picker import upload_button
    from .features.scan import ScanAPI, scan
    from .features.biometrics import BiometricsAPI, biometrics
    from .features.sensors import SensorsAPI, sensors, BatteryAPI, battery
    from .features.bluetooth import BluetoothAPI, bluetooth
    from .features.nfc import NfcAPI, nfc
    from .features.contacts import ContactsAPI, contacts
    from .features.ble import BleAPI, ble
    from .features.billing import BillingAPI, billing
    from .features.flashlight import FlashlightAPI, flashlight
    from .features.wallpaper import WallpaperAPI, wallpaper
    from .features.camera_view import camera_view
    from .features.native import NativeAPI, native
    from .features.kit import (
        HapticsAPI, haptics, SpeechAPI, speech, BrowserAPI, browser,
        DownloadsAPI, downloads, CalendarAPI, calendar, PhoneAPI, phone,
        RecorderAPI, recorder, PrintingAPI, printing, IncomingAPI, incoming,
        HomeWidgetAPI, home_widget, QuickTileAPI, quick_tile, AdsAPI, ads,
        UpdatesAPI, updates, HealthAPI, health, TimerAPI, timer,
        NetworkAPI, network, DisplayAPI, display, AppLockAPI, app_lock,
    )
    from .features.data import (
        DataCoreError, FieldDef, IndexDef, FilterDef, OrderDef, ModelDef,
        SchemaDef, MigrationDef, MigrationOperation, TransactionContext,
        RelationDef, QuerySubscription,
    )
    from .maps import LocationSample, map_view
    from .routes import RouteAPI, route_points, routes

    # A job body that reaches a screen call is refused here with the same
    # words the build uses -- see apkpy_lib/job_rules.py.
    from . import ui as _ui
    from . import job_rules as _job_rules
    _job_rules.install_preview_guards(globals(), vars(_ui))

    __all__ = [
        'Screen', 'ReactiveState', 'state', 'lifecycle', 'bottom_nav', 'BottomNav', 'mini_player', 'app_bar', 'sliver_app_bar', 'action', 'on_click_navigate', 'back', 'button', 'label', 'inputs', 'input_field', 'validate', 'image', 'view_image', 'video', 'avatar', 'container', 'card', 'card_action', 'drawer', 'DrawerDef', 'font', 'row', 'column', 'responsive', 'list_row', 'list_view', 'virtual_collection', 'swipe', 'SwipeAction', 'pager', 'tab', 'PagerDef', 'chart', 'ChartDef', 'chips', 'segmented', 'ChoiceDef', 'carousel', 'grid', 'spinner', 'skeleton', 'empty_state', 'error_state', 'OverlayDef', 'bottom_sheet', 'modal', 'menu', 'popup_menu', 'context_menu', 'snackbar', 'tooltip', 'date_picker', 'time_picker', 'run', 'toast', 'notify', 'share',
        'declare_permissions', 'permissions', 'PermissionsAPI', 'storage', 'StorageAPI', 'appearance', 'AppearanceAPI', 'translations', 't', 'language', 'LanguageAPI', 'crash', 'CrashAPI', 'scan', 'ScanAPI', 'app', 'AppAPI', 'crypto', 'CryptoAPI', 'db', 'SQLiteAPI', 'https', 'HttpsAPI', 'json_get',
        'service', 'ServiceAPI', 'clipboard', 'ClipboardAPI', 'camera', 'CameraAPI', 'gallery', 'GalleryAPI',
        'location', 'LocationAPI', 'alert', 'confirm', 'device', 'random', 'RandomAPI', 'datetime', 'DatetimeAPI', 'audio', 'AudioAPI', 'files', 'FilesAPI', 'uploads', 'UploadsAPI',
        'auth', 'AuthAPI', 'apps', 'AppsAPI', 'websocket', 'WebSocketAPI',
        'push', 'PushAPI', 'map_view', 'LocationSample',
        'notifications', 'NotificationsAPI',
        'routes', 'RouteAPI', 'route_points',
        'markdown', 'rich_text', 'tree_view', 'Theme',
        'background_job', 'JobDef', 'JobStatus',
        'upload_button',
        'biometrics', 'BiometricsAPI',
        'sensors', 'SensorsAPI', 'battery', 'BatteryAPI',
        'bluetooth', 'BluetoothAPI', 'ble', 'BleAPI',
        'nfc', 'NfcAPI',
        'native', 'NativeAPI',
        'haptics', 'HapticsAPI', 'speech', 'SpeechAPI', 'browser', 'BrowserAPI',
        'downloads', 'DownloadsAPI', 'calendar', 'CalendarAPI',
        'phone', 'PhoneAPI', 'recorder', 'RecorderAPI',
        'printing', 'PrintingAPI', 'incoming', 'IncomingAPI',
        'home_widget', 'HomeWidgetAPI', 'quick_tile', 'QuickTileAPI',
        'ads', 'AdsAPI', 'updates', 'UpdatesAPI', 'health', 'HealthAPI',
        'timer', 'TimerAPI', 'network', 'NetworkAPI', 'display', 'DisplayAPI', 'app_lock', 'AppLockAPI',
        'contacts', 'ContactsAPI',
        'billing', 'BillingAPI', 'secure_screen',
        'flashlight', 'FlashlightAPI',
        'wallpaper', 'WallpaperAPI',
        'camera_view',
        'DataCoreError', 'FieldDef', 'IndexDef', 'FilterDef', 'OrderDef',
        'ModelDef', 'SchemaDef', 'MigrationDef', 'MigrationOperation',
        'TransactionContext', 'RelationDef', 'QuerySubscription'
    ]

    # Compiler hosts manage a structured error channel of their own and skip
    # this process-wide desktop hook.
    from .diagnostics import install_exception_hook as _install_exception_hook
    _install_exception_hook()
else:
    __all__ = []

