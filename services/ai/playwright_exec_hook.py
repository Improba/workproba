"""Runtime hook PyInstaller : bit exécutable du driver Node Playwright."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _chmod_playwright_driver() -> None:
    mei = getattr(sys, "_MEIPASS", None)
    if not mei:
        return
    driver = Path(mei) / "playwright" / "driver"
    if not driver.is_dir():
        return
    for name in ("node", "node.exe"):
        path = driver / name
        if not path.is_file():
            continue
        try:
            path.chmod(path.stat().st_mode | 0o755)
        except OSError:
            pass


_chmod_playwright_driver()
os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
