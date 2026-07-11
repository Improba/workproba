"""Tests endpoint POST /agent/reprocess-attachment."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import app.auth as authmod
import app.main as mainmod
from app.agent.attachments import (
    attachment_relative_path,
    persist_attachment_file,
    reprocess_attachment,
)
from app.limits import DEFAULT_LIMITS
from app.llm.provider_sets import MISTRAL_BUILTIN_SET
from app.ocr.mistral import OcrResult


@pytest.fixture(autouse=True)
def _loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _headers() -> dict[str, str]:
    return {"X-Internal-Secret": "desktop-dev-secret"}


def _ocr_set() -> dict:
    data = MISTRAL_BUILTIN_SET.model_copy(
        update={
            "chat": MISTRAL_BUILTIN_SET.chat.model_copy(
                update={"api_key": SecretStr("test-key")}
            ),
            "capabilities": MISTRAL_BUILTIN_SET.capabilities.model_copy(
                update={"vision": False}
            ),
        }
    )
    return data.model_dump(mode="json")


async def test_persist_and_reprocess_scanned_pdf(tmp_path: Path) -> None:
    session_id = "sess-1"
    attachment_id = "att-1"
    file_name = "scan.pdf"
    relative = attachment_relative_path(session_id, attachment_id, file_name)
    content = b"%PDF-1.4 scanned"
    persist_attachment_file(
        tmp_path,
        session_id=session_id,
        attachment_id=attachment_id,
        file_name=file_name,
        content=content,
        file_path=relative,
    )

    ocr_set = MISTRAL_BUILTIN_SET.model_copy(
        update={
            "chat": MISTRAL_BUILTIN_SET.chat.model_copy(
                update={"api_key": SecretStr("test-key")}
            ),
        }
    )

    with (
        patch("app.agent.attachments.is_scanned_pdf", return_value=True),
        patch(
            "app.agent.attachments.MistralOcrClient.ocr_pdf",
            new_callable=AsyncMock,
            return_value=OcrResult(text="texte ocr", pages_processed=1, metadata={}),
        ),
    ):
        result = await reprocess_attachment(
            workspace_data_dir=tmp_path,
            attachment_id=attachment_id,
            file_path=relative,
            file_name=file_name,
            mime_type="application/pdf",
            limits=DEFAULT_LIMITS,
            provider_set=ocr_set,
        )

    assert result.status_key == "scanned_pdf"
    assert "PDF scanné" in result.label_locale


def test_reprocess_endpoint_persist_only(tmp_path: Path) -> None:
    session_id = "sess-2"
    attachment_id = "att-2"
    relative = attachment_relative_path(session_id, attachment_id, "note.txt")
    payload = {
        "workspace_data_dir": str(tmp_path),
        "project_path": str(tmp_path),
        "attachment_id": attachment_id,
        "file_path": relative,
        "mime_type": "text/plain",
        "content_base64": base64.b64encode(b"hello").decode("ascii"),
        "persist_only": True,
    }

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/reprocess-attachment",
            json=payload,
            headers=_headers(),
        )

    assert resp.status_code == 200
    assert resp.json()["status_key"] == "stored"
    assert (tmp_path / relative).is_file()


def test_reprocess_endpoint_rejects_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    payload = {
        "workspace_data_dir": str(tmp_path),
        "project_path": str(tmp_path),
        "attachment_id": "att-x",
        "file_path": "../outside.txt",
        "mime_type": "text/plain",
    }

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/agent/reprocess-attachment",
            json=payload,
            headers=_headers(),
        )

    assert resp.status_code == 403


def test_reprocess_endpoint_with_ocr_set(tmp_path: Path) -> None:
    session_id = "sess-3"
    attachment_id = "att-3"
    relative = attachment_relative_path(session_id, attachment_id, "scan.pdf")
    (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / relative).write_bytes(b"%PDF-1.4")

    payload = {
        "workspace_data_dir": str(tmp_path),
        "project_path": str(tmp_path),
        "attachment_id": attachment_id,
        "file_path": relative,
        "mime_type": "application/pdf",
        "provider_set": _ocr_set(),
    }

    with (
        patch("app.agent.attachments.is_scanned_pdf", return_value=True),
        patch(
            "app.agent.attachments.MistralOcrClient.ocr_pdf",
            new_callable=AsyncMock,
            return_value=OcrResult(text="ocr ok", pages_processed=1, metadata={}),
        ),
        TestClient(mainmod.app) as client,
    ):
        resp = client.post(
            "/agent/reprocess-attachment",
            json=payload,
            headers=_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status_key"] == "scanned_pdf"
