"""AndroidManifest.xml."""
from ..features import push as push_feature
from ..features import native as native_feature
from ..features import flashlight as flashlight_feature
from ..features import sensors as sensors_feature


def _permission_symbol(entry):
    """The bare permission name.

    An entry may carry manifest attributes as ``NAME|attr=value``, and a
    vendor permission carries a package. Everything that builds a Java
    identifier from it -- PERMISSION_REQ_*, the switch arms -- has to see a
    bare word, or javac stops on
    ``PERMISSION_REQ_BLUETOOTH|maxSdkVersion=30`` or on
    ``PERMISSION_REQ_com.android.vending.BILLING``.
    """
    name = str(entry).partition('|')[0].strip()
    # A vendor permission carries a package (com.android.vending.BILLING), and
    # the dots are not legal in an identifier. Only the last segment names it,
    # in upper case as Android spells every one ("camera" is CAMERA).
    return (name.rpartition('.')[2] or name).upper()


def _generate_manifest(screen_ids, start_screen_id, package="com.apkpy.app", declared_permissions=None, needs_file_provider=False, bottom_nav_info=None, needs_media_service=False, needs_push=False, needs_location_service=False, auth=None, pinned=False, needs_flash=False, sensors_used=(), orientations=None):
    """Gera o conteúdo do AndroidManifest.xml com todas as Activities, permissões e providers."""
    declared_permissions = declared_permissions or []
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<manifest xmlns:android="http://schemas.android.com/apk/res/android"',
        f'    package="{package}">',
        '',
    ]
    
    # A permission is normally just its name. Bluetooth needs more: the legacy
    # BLUETOOTH/BLUETOOTH_ADMIN pair and the location grant that discovery used
    # to require must stop at API 30, or an app that never wants location keeps
    # asking for it on modern phones -- which the Play Store flags and users
    # read as spyware. So an entry may also be "NAME|attr=value|attr=value".
    _written_permissions = set()
    for perm in declared_permissions:
        name, _, extra = str(perm).partition('|')
        attributes = ''
        for pair in (part for part in extra.split('|') if part):
            key, _, value = pair.partition('=')
            attributes += f' android:{key}="{value}"'
        # Most permissions live under android.permission, but not all: Play
        # billing is com.android.vending.BILLING, and prefixing that produced a
        # name no Android has ever heard of. A name that already carries a
        # package is used as it stands.
        qualified = name if '.' in name else 'android.permission.%s' % name.strip().upper()
        _permission_line = (
            f'    <uses-permission android:name="{qualified}"'
            f'{attributes} />')
        # "INTERNET" from an https call and the whole name from a native block
        # are one permission, and it is asked for once.
        if _permission_line in _written_permissions:
            continue
        _written_permissions.add(_permission_line)
        lines.append(_permission_line)
    if declared_permissions:
        lines.append('')

    # flashlight.* asks for no permission at all -- setTorchMode is not camera
    # access. What it does deserve is an honest description of the hardware it
    # touches, and required="false" so the Play Store still shows the app to
    # phones without a flash. Those get "no_flash" and carry on.
    if needs_flash:
        lines.extend(flashlight_feature.manifest_features())
        lines.append('')

    # Same reasoning for the sensors: describe what is touched, require
    # nothing, so a phone without a step counter still installs the app.
    if sensors_used:
        lines.extend(sensors_feature.manifest_features(sensors_used))
        lines.append('')

    # native.manifest(feature=) / native.manifest(xml=). As permissoes seguem
    # o caminho normal, por declared_permissions.
    _native_manifest = native_feature.manifest_lines()
    if _native_manifest:
        lines.extend(_native_manifest)
        lines.append('')

    lines += [
        '    <application',
        '        android:allowBackup="true"',
        # Backup copies SharedPreferences to a new phone; the AES key that
        # encrypted them lives in that phone's Keystore and does not travel.
        # Without these rules a restored app decrypts everything to "" and
        # reports it as "never saved" -- silent data loss, months after the
        # fact. The rules keep the encrypted file at home instead.
        '        android:dataExtractionRules="@xml/apkpy_backup_rules"',
    ] + ([
        # Pinning e configuracao, nao codigo: o Android aplica-a por baixo
        # de todas as bibliotecas de rede da app. Feito em codigo, so'
        # cobriria os pedidos que se lembrassem de perguntar.
        '        android:networkSecurityConfig="@xml/apkpy_network_security"',
    ] if pinned else []) + [
        '        android:fullBackupContent="@xml/apkpy_backup_legacy"',
        '        android:label="ApkPy App"',
        '        android:supportsRtl="true"',
        # Material widgets validate their context theme during layout inflation.
        # AppCompat compiles, but crashes when opening a screen containing a
        # MaterialCardView/MaterialToolbar. DayNight supports both Theme modes;
        # NoActionBar leaves room for ApkPy's own app bars.
        '        android:theme="@style/Theme.App">',
        '',
    ]

    for sid in screen_ids:
        class_name = f"Screen_{sid}Activity"
        launch_mode = ' android:launchMode="singleTop"' if bottom_nav_info else ''
        # Screen(orientation=) / run(orientation=): which way up the screen is
        # from its first frame, before any of the app's code has run.
        launch_mode += (orientations or {}).get(sid, '')
        if sid == start_screen_id:
            lines += [
                f'        <activity android:name=".{class_name}"{launch_mode} android:exported="true">',
                f'            <intent-filter>',
                f'                <action android:name="android.intent.action.MAIN" />',
                f'                <category android:name="android.intent.category.LAUNCHER" />',
                f'            </intent-filter>',
                f'        </activity>',
                '',
            ]
        else:
            lines.append(f'        <activity android:name=".{class_name}"{launch_mode} />')
            lines.append('')

    # FileProvider — necessário para camera.capture() partilhar o ficheiro da
    # foto com a app de câmara nativa via content:// URI (em vez de file://).
    if needs_file_provider:
        lines += [
            '        <provider',
            '            android:name="androidx.core.content.FileProvider"',
            '            android:authorities="${applicationId}.fileprovider"',
            '            android:exported="false"',
            '            android:grantUriPermissions="true">',
            '            <meta-data',
            '                android:name="android.support.FILE_PROVIDER_PATHS"',
            '                android:resource="@xml/file_paths" />',
            '        </provider>',
            '',
        ]

    # Foreground media service (audio.play_background) — toca com o ecrã apagado.
    if needs_media_service:
        lines += [
            '        <service',
            '            android:name=".ApkpyMediaService"',
            '            android:exported="false"',
            '            android:foregroundServiceType="mediaPlayback" />',
            '',
        ]

    if needs_location_service:
        lines += [
            '        <service',
            '            android:name=".ApkpyLocationService"',
            '            android:exported="false"',
            '            android:foregroundServiceType="location" />',
            '',
        ]

    # Login OAuth (auth.login) — Activity recetora do redirect (deep-link). O
    # intent-filter casa o scheme/host do redirect_uri (ex.: apkpy://auth).
    if needs_push:
        lines += push_feature.manifest_service_lines()

    if auth:
        _scheme = auth.get('scheme', 'apkpy')
        _host = auth.get('host', 'auth')
        lines += [
            '        <activity',
            '            android:name=".ApkpyAuthActivity"',
            '            android:exported="true"',
            '            android:launchMode="singleTask">',
            '            <intent-filter>',
            '                <action android:name="android.intent.action.VIEW" />',
            '                <category android:name="android.intent.category.DEFAULT" />',
            '                <category android:name="android.intent.category.BROWSABLE" />',
            f'                <data android:scheme="{_scheme}" android:host="{_host}" />',
            '            </intent-filter>',
            '        </activity>',
            '',
        ]

    # native.manifest(xml=) for what lives inside <application>: a service,
    # a receiver, an activity of an SDK.
    _native_application = native_feature.application_lines()
    if _native_application:
        lines.extend(_native_application)
        lines.append('')

    lines += ['    </application>', '', '</manifest>']
    return "\n".join(lines)
