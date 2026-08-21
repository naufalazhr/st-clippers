# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import cv2
cv2_dir = os.path.dirname(cv2.__file__)
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime"),
    datas=collect_data_files("yt_dlp") + collect_data_files("faster_whisper") + [
        ("models", "models"),
        ("fonts", "fonts"),
        (os.path.join(cv2_dir, "data"), "cv2/data"),
    ],
    hiddenimports=[
        "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan", "uvicorn.lifespan.on",
        "faster_whisper", "ctranslate2", "yt_dlp", "multipart",
        "clipper", "model_cache", "llm", "safe_path",
    ],
    excludes=["torch", "nvidia", "nvidia.cublas", "nvidia.cudnn", "tkinter", "unittest", "pydoc"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="sultanclip-backend", debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name="sultanclip-backend")
