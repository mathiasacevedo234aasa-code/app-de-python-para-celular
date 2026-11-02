[app]
title = PyStudio
package.name = pystudio
package.domain = org.pystudio
source.dir = .
source.include_exts = py,png,jpg,kv,json,txt,pem
source.exclude_dirs = bin,.buildozer,.github,__pycache__
version = 1.0.0

# Solo recetas compiladas. Las librerías de Python puro (pygments, requests...)
# se copian a vendor/ en el workflow, porque el pip interno de p4a falla al instalarlas.
requirements = python3,kivy==2.3.1

orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.enable_androidx = True
android.window_soft_input_mode = adjustResize

[buildozer]
log_level = 2
warn_on_root = 1
