from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent.tools import build_session_digests


def _write_session(
    conv_dir: Path,
    session_id: str,
    *,
    title: str,
    updated_at: str,
    summary: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "id": session_id,
        "workspaceId": "w",
        "folderPath": "/tmp/project",
        "title": title,
        "messages": messages or [],
        "reasoningEffort": "medium",
        "model": "test-model",
        "createdAt": "2026-07-10T08:00:00Z",
        "updatedAt": updated_at,
    }
    if summary is not None:
        payload["summary"] = summary
    (conv_dir / f"{session_id}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_build_session_digests_excludes_current_sorts_and_falls_back(
    tmp_path: Path,
) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    _write_session(
        conv_dir,
        "current",
        title="Active session",
        updated_at="2026-07-10T12:00:00Z",
        summary="Must be excluded",
    )
    _write_session(
        conv_dir,
        "with-summary",
        title="Marge Q2",
        updated_at="2026-07-10T10:00:00Z",
        summary="Synthese persistante sur la marge.",
    )
    _write_session(
        conv_dir,
        "without-summary",
        title="Budget",
        updated_at="2026-07-10T11:00:00Z",
        messages=[
            {"role": "assistant", "content": "Bonjour"},
            {
                "role": "user",
                "content": "Peux-tu analyser le budget annuel et proposer une synthese?",
            },
            {"role": "assistant", "content": "Premiere reponse"},
            {
                "role": "assistant",
                "content": "Derniere reponse avec les points importants.",
            },
        ],
    )
    (conv_dir / "broken.json").write_text("{not json", encoding="utf-8")

    result = build_session_digests(tmp_path, "current")

    assert result["count"] == 2
    assert result["total_available"] == 2
    assert [session["id"] for session in result["sessions"]] == [
        "without-summary",
        "with-summary",
    ]
    assert "current" not in {session["id"] for session in result["sessions"]}
    by_id = {session["id"]: session for session in result["sessions"]}
    assert by_id["with-summary"]["summary"] == "Synthese persistante sur la marge."
    assert "Peux-tu analyser le budget annuel" in by_id["without-summary"]["summary"]
    assert "Derniere reponse" in by_id["without-summary"]["summary"]


def test_build_session_digests_filters_by_query(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    _write_session(
        conv_dir,
        "finance",
        title="Marge Q2",
        updated_at="2026-07-10T10:00:00Z",
        summary="Synthese persistante sur la marge.",
    )
    _write_session(
        conv_dir,
        "ops",
        title="Support",
        updated_at="2026-07-10T11:00:00Z",
        summary="Notes sur les incidents clients.",
    )

    result = build_session_digests(tmp_path, "current", query="MARGE")

    assert result["count"] == 1
    assert result["total_available"] == 2
    assert result["sessions"][0]["id"] == "finance"


def test_build_session_digests_excludes_current_by_stem(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    payload = {
        "id": "sess_other",
        "title": "Other",
        "updatedAt": "2026-07-10T12:00:00Z",
        "summary": "Autre fil",
    }
    (conv_dir / "current.json").write_text(
        json.dumps({**payload, "id": "sess_current", "summary": "Courant"}),
        encoding="utf-8",
    )

    result = build_session_digests(tmp_path, "current")

    assert result["count"] == 0


def test_build_session_digests_caps_to_twenty(tmp_path: Path) -> None:
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    for i in range(25):
        _write_session(
            conv_dir,
            f"s{i:02d}",
            title=f"Session {i}",
            updated_at=f"2026-07-10T00:{i:02d}:00Z",
            summary=f"Summary {i}",
        )

    result = build_session_digests(tmp_path, "current")

    assert result["count"] == 20
    assert result["total_available"] == 25
    assert result["sessions"][0]["id"] == "s24"
    assert result["sessions"][-1]["id"] == "s05"
