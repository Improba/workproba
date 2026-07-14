# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

hiddenimports: list[str] = []
datas: list = []
binaries: list = []

collect_packages = [
    "uvicorn",
    "fastapi",
    "starlette",
    "sse_starlette",
    "litellm",
    "pydantic_ai",
    "pydantic_ai_slim",
    "sqlite_vec",
    "pdfplumber",
    "httpx",
    "pydantic",
    "pydantic_settings",
    "openai",
    "openpyxl",
    "docx",
    "pptx",
    "reportlab",
    "anyio",
    "sniffio",
    "h11",
    "httptools",
    "uvloop",
    "websockets",
    "watchfiles",
    "click",
    "tiktoken",
    "tiktoken_ext",
    "jinja2",
    "tokenizers",
    "genai_prices",
]

for package in collect_packages:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("tiktoken_ext")

a = Analysis(
    ["workproba_ai_entry.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["playwright"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Onefile: un seul binaire, pas de dossier _internal à côté du sidecar Tauri au runtime.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="workproba-ai",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
