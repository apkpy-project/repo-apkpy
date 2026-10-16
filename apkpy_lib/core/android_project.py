"""Headless Android project packaging for ApkPy Studio and desktop tools.

The Builder must never execute user Python.  This module takes the successful
in-process compilation result and creates a complete Gradle project containing
only generated Java/XML/resources.  It deliberately has no dependency on the
desktop CLI, Click or Tkinter.
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import Dict, Mapping, Union

from ..config import COMPILE_SDK, MIN_SDK, TARGET_SDK
from .app_ir import CompileResult


ProjectEntry = Union[str, bytes]


def write_android_project_zip(
    result: CompileResult,
    destination: Union[str, os.PathLike[str]],
    *,
    app_name: str = "ApkPy App",
    application_id: str = "com.apkpy.app",
    version_code: int = 1,
    version_name: str = "1.0",
) -> Mapping[str, object]:
    """Write a buildable, Python-free Android project archive.

    ``result`` must be the live ``CompileResult`` returned by ``compile_to_ir``
    because it carries the already prepared compiler analysis.  No second AST
    analysis is performed by the Java/XML backend.
    """
    if not result.ok or result.ir is None:
        raise ValueError("A successful CompileResult is required")
    package_name = _safe_application_id(application_id)
    generated = result.generate_android_files(package=package_name)
    entries = _project_entries(
        generated,
        app_name=app_name,
        package_name=package_name,
        version_code=version_code,
        version_name=version_name,
    )
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            value = entries[name]
            archive.writestr(name.replace("\\", "/"), value)
    return {
        "path": str(target),
        "applicationId": package_name,
        "entryCount": len(entries),
        "pythonIncluded": False,
    }


def _project_entries(
    generated: Mapping[str, object],
    *,
    app_name: str,
    package_name: str,
    version_code: int,
    version_name: str,
) -> Dict[str, ProjectEntry]:
    all_text = "\n".join(
        value for value in generated.values() if isinstance(value, str)
    )
    dependencies = [
        "implementation 'androidx.appcompat:appcompat:1.6.1'",
        "implementation 'com.google.android.material:material:1.11.0'",
        "implementation 'androidx.constraintlayout:constraintlayout:2.1.4'",
    ]
    optional = (
        ("androidx.recyclerview.widget.RecyclerView", "implementation 'androidx.recyclerview:recyclerview:1.3.2'"),
        ("androidx.drawerlayout.widget.DrawerLayout", "implementation 'androidx.drawerlayout:drawerlayout:1.2.0'"),
        ("androidx.swiperefreshlayout.widget.SwipeRefreshLayout", "implementation 'androidx.swiperefreshlayout:swiperefreshlayout:1.2.0'"),
        ("androidx.work.", "implementation 'androidx.work:work-runtime:2.9.0'"),
        ("okhttp3.", "implementation 'com.squareup.okhttp3:okhttp:5.3.2'"),
        ("androidx.media3.", "implementation 'androidx.media3:media3-exoplayer:1.3.1'\n    implementation 'androidx.media3:media3-exoplayer-hls:1.3.1'\n    implementation 'androidx.media3:media3-exoplayer-dash:1.3.1'\n    implementation 'androidx.media3:media3-ui:1.3.1'"),
        ("com.google.android.gms.location", "implementation 'com.google.android.gms:play-services-location:21.3.0'"),
    )
    for marker, dependency in optional:
        if marker in all_text and dependency not in dependencies:
            dependencies.append(dependency)

    safe_name = str(app_name or "ApkPy App").replace('"', "'")
    entries: Dict[str, ProjectEntry] = {
        "settings.gradle": _settings_gradle(safe_name),
        "build.gradle": _root_build_gradle(),
        "gradle.properties": (
            "android.useAndroidX=true\n"
            "android.enableJetifier=true\n"
            "org.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8\n"
        ),
        "gradle/wrapper/gradle-wrapper.properties": (
            "distributionBase=GRADLE_USER_HOME\n"
            "distributionPath=wrapper/dists\n"
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip\n"
            "zipStoreBase=GRADLE_USER_HOME\n"
            "zipStorePath=wrapper/dists\n"
        ),
        "app/build.gradle": _app_build_gradle(
            package_name, version_code, version_name, dependencies,
        ),
    }

    package_path = package_name.replace(".", "/")
    for relative, content in generated.items():
        if relative.startswith("java/"):
            output = "app/src/main/java/%s/%s" % (
                package_path, os.path.basename(relative),
            )
        elif relative.startswith("res/"):
            output = "app/src/main/" + relative
        elif relative == "AndroidManifest.xml":
            output = "app/src/main/AndroidManifest.xml"
        else:
            output = "app/" + relative

        if isinstance(content, tuple) and len(content) >= 2 and content[0] == "COPY_FILE":
            source = Path(str(content[1]))
            if not source.is_file():
                raise FileNotFoundError("Asset not found: %s" % source)
            entries[output] = source.read_bytes()
        elif isinstance(content, str):
            if relative == "AndroidManifest.xml":
                content = re.sub(r'\s*package="[^"]*"', "", content, count=1)
                content = re.sub(
                    r'android:label="[^"]*"',
                    'android:label="%s"' % _xml_attribute(safe_name),
                    content,
                    count=1,
                )
            entries[output] = content
        else:
            raise TypeError("Unsupported generated entry: %s" % relative)
    return entries


def _settings_gradle(name: str) -> str:
    return """pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = \"%s\"
include ':app'
""" % name


def _root_build_gradle() -> str:
    return """plugins {
    id 'com.android.application' version '8.6.1' apply false
}
"""


def _app_build_gradle(
    package_name: str,
    version_code: int,
    version_name: str,
    dependencies: list[str],
) -> str:
    return """plugins { id 'com.android.application' }

android {
    namespace '%s'
    compileSdk %d
    defaultConfig {
        applicationId '%s'
        minSdk %d
        targetSdk %d
        versionCode %d
        versionName '%s'
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}

dependencies {
    %s
}
""" % (
        package_name, COMPILE_SDK, package_name, MIN_SDK, TARGET_SDK,
        max(1, int(version_code)),
        str(version_name).replace("'", ""), "\n    ".join(dependencies),
    )


def _safe_application_id(value: str) -> str:
    parts = [re.sub(r"[^A-Za-z0-9_]", "_", item) for item in str(value).split(".")]
    if len(parts) < 2 or any(not item for item in parts):
        raise ValueError("application_id must contain at least two valid segments")
    parts = [("app_" + item) if item[0].isdigit() else item for item in parts]
    return ".".join(parts)


def _xml_attribute(value: str) -> str:
    return (value.replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))
