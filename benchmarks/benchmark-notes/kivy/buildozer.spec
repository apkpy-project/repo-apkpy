[app]
title = Benchmark Notes
package.name = benchmarknoteskivy
package.domain = com.apkpy.benchmark
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1.0
requirements = python3,kivy==2.3.1
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.api = 35
android.minapi = 24
android.archs = arm64-v8a
