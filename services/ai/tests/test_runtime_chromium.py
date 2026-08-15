"""Probe Chromium bundlé (pas de lancement navigateur)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime_chromium import (
    ChromiumUnavailable,
    chromium_available,
    chromium_launch_args,
    find_chromium_build_dir,
    health_chromium_status,
    require_chromium,
    reset_chromium_probe_cache,
)


@pytest.fixture(autouse=True)
def _clear_probe() -> None:
    reset_chromium_probe_cache()
    yield
    reset_chromium_probe_cache()


def _fake_build(root: Path, name: str = "chromium-1234") -> Path:
    build = root / name
    (build / "chrome-linux64").mkdir(parents=True)
    (build / "chrome-linux64" / "chrome").write_bytes(b"\x7fELF")
    return build


def test_find_chromium_build_dir(tmp_path: Path) -> None:
    build = _fake_build(tmp_path)
    assert find_chromium_build_dir([tmp_path]) == build


def test_find_chromium_ignores_headless_shell_only(tmp_path: Path) -> None:
    shell = tmp_path / "chromium_headless_shell-1228" / "chrome-headless-shell-linux64"
    shell.mkdir(parents=True)
    (shell / "chrome-headless-shell").write_bytes(b"\x7fELF")
    assert find_chromium_build_dir([tmp_path]) is None


def test_find_chromium_missing_dir(tmp_path: Path) -> None:
    assert find_chromium_build_dir([tmp_path / "absent"]) is None


def test_frozen_prefers_driver_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_build(tmp_path, "chromium-1")
    expected = _fake_build(tmp_path, "chromium-1228")
    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: True)
    monkeypatch.setattr(
        "app.runtime_chromium.playwright_chromium_revision", lambda: "1228"
    )
    assert find_chromium_build_dir([tmp_path]) == expected


def test_frozen_rejects_other_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_build(tmp_path, "chromium-1")
    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: True)
    monkeypatch.setattr(
        "app.runtime_chromium.playwright_chromium_revision", lambda: "1228"
    )
    assert find_chromium_build_dir([tmp_path]) is None


def test_playwright_pip_spec_matches_pyproject() -> None:
    from app.runtime_chromium import PLAYWRIGHT_PIP_SPEC

    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert f'"{PLAYWRIGHT_PIP_SPEC}"' in pyproject


def test_frozen_roots_only_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.runtime_chromium import playwright_browsers_roots

    bundled = tmp_path / "bundled"
    bundled.mkdir()
    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: True)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(bundled))
    assert playwright_browsers_roots() == [bundled]


def test_frozen_roots_empty_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.runtime_chromium import playwright_browsers_roots

    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: True)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    assert playwright_browsers_roots() == []


def test_chromium_available_false_without_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("playwright")
    monkeypatch.setattr(
        "app.runtime_chromium.playwright_browsers_roots",
        lambda: [tmp_path / "empty"],
    )
    assert chromium_available() is False
    assert health_chromium_status() == "missing"


def test_chromium_available_true_with_fake_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("playwright")
    _fake_build(tmp_path)
    monkeypatch.setattr(
        "app.runtime_chromium.playwright_browsers_roots",
        lambda: [tmp_path],
    )
    assert chromium_available() is True
    assert health_chromium_status() == "ready"


def test_require_chromium_frozen_does_not_pip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: True)
    monkeypatch.setattr(
        "app.runtime_chromium.playwright_browsers_roots",
        lambda: [tmp_path],
    )
    called = {"pip": False}

    def _boom(*_a: object, **_k: object) -> None:
        called["pip"] = True
        raise AssertionError("pip must not run when frozen")

    monkeypatch.setattr("app.runtime_chromium._dev_install_chromium", _boom)
    with pytest.raises(ChromiumUnavailable):
        require_chromium(allow_dev_install=True)
    assert called["pip"] is False


def test_chromium_launch_uses_bundled_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.runtime_chromium import chromium_launch_kwargs

    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: True)
    assert "--no-sandbox" in chromium_launch_args()
    monkeypatch.setattr("app.runtime_chromium.is_frozen", lambda: False)
    assert "--no-sandbox" not in chromium_launch_args()
    kwargs = chromium_launch_kwargs()
    assert kwargs["headless"] is True
    assert kwargs["channel"] == "chromium"
    assert "executable_path" not in kwargs
    assert "args" in kwargs
