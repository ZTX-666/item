from __future__ import annotations

import json

import pytest

from agent_toolbox.config import settings
from agent_toolbox.registry import tool_specs
from agent_toolbox.tools.feishu import (
    FeishuSendFileRequest,
    FeishuSendImageRequest,
    feishu_send_file_message,
    feishu_send_image_message,
)


class FakeResponse:
    def __init__(self, data: dict, status_code: int = 200, ok: bool = True) -> None:
        self._data = data
        self.status_code = status_code
        self.ok = ok
        self.text = json.dumps(data, ensure_ascii=False)

    def json(self) -> dict:
        return self._data


@pytest.fixture()
def configured_feishu_settings():
    values = {
        "feishu_app_id": "test-app-id",
        "feishu_app_secret": "test-app-secret",
        "feishu_api_base_url": "https://feishu.test",
    }
    originals = {name: getattr(settings, name) for name in values}
    for name, value in values.items():
        object.__setattr__(settings, name, value)
    yield
    for name, value in originals.items():
        object.__setattr__(settings, name, value)


def test_send_image_message_uploads_image_then_sends_image(monkeypatch, configured_feishu_settings, tmp_path):
    image_path = tmp_path / "hazard.png"
    image_path.write_bytes(b"fake-png-bytes")
    calls: list[dict] = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if url.endswith("/open-apis/auth/v3/tenant_access_token/internal"):
            assert kwargs["json"] == {"app_id": "test-app-id", "app_secret": "test-app-secret"}
            return FakeResponse({"code": 0, "tenant_access_token": "tenant-token"})
        if url.endswith("/open-apis/im/v1/images"):
            assert kwargs["headers"] == {"Authorization": "Bearer tenant-token"}
            assert kwargs["data"] == {"image_type": "message"}
            filename, file_obj = kwargs["files"]["image"][:2]
            assert filename == "hazard.png"
            assert file_obj.read() == b"fake-png-bytes"
            return FakeResponse({"code": 0, "data": {"image_key": "img_v2_test"}})
        if url.endswith("/open-apis/im/v1/messages"):
            assert kwargs["headers"]["Authorization"] == "Bearer tenant-token"
            assert kwargs["params"] == {"receive_id_type": "open_id"}
            assert kwargs["json"] == {
                "receive_id": "ou_test_user",
                "msg_type": "image",
                "content": json.dumps({"image_key": "img_v2_test"}, ensure_ascii=False),
            }
            return FakeResponse({"code": 0, "data": {"message_id": "om_test"}})
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("agent_toolbox.tools.feishu.requests.post", fake_post)

    result = feishu_send_image_message(
        FeishuSendImageRequest(receive_id="ou_test_user", receive_id_type="open_id", image_path=str(image_path))
    )

    assert result.ok is True
    assert result.data["image_key"] == "img_v2_test"
    assert result.data["request_payload"]["msg_type"] == "image"
    assert [call["url"] for call in calls] == [
        "https://feishu.test/open-apis/auth/v3/tenant_access_token/internal",
        "https://feishu.test/open-apis/im/v1/images",
        "https://feishu.test/open-apis/im/v1/messages",
    ]


def test_send_file_message_uploads_file_then_sends_file(monkeypatch, configured_feishu_settings, tmp_path):
    file_path = tmp_path / "safety.pdf"
    file_path.write_bytes(b"%PDF-test")

    def fake_post(url, **kwargs):
        if url.endswith("/open-apis/auth/v3/tenant_access_token/internal"):
            return FakeResponse({"code": 0, "tenant_access_token": "tenant-token"})
        if url.endswith("/open-apis/im/v1/files"):
            assert kwargs["headers"] == {"Authorization": "Bearer tenant-token"}
            assert kwargs["data"] == {"file_type": "pdf", "file_name": "safety.pdf"}
            filename, file_obj = kwargs["files"]["file"][:2]
            assert filename == "safety.pdf"
            assert file_obj.read() == b"%PDF-test"
            return FakeResponse({"code": 0, "data": {"file_key": "file_v2_test"}})
        if url.endswith("/open-apis/im/v1/messages"):
            assert kwargs["params"] == {"receive_id_type": "chat_id"}
            assert kwargs["json"] == {
                "receive_id": "oc_test_chat",
                "msg_type": "file",
                "content": json.dumps({"file_key": "file_v2_test"}, ensure_ascii=False),
            }
            return FakeResponse({"code": 0, "data": {"message_id": "om_file"}})
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("agent_toolbox.tools.feishu.requests.post", fake_post)

    result = feishu_send_file_message(
        FeishuSendFileRequest(
            receive_id="oc_test_chat",
            receive_id_type="chat_id",
            file_path=str(file_path),
            file_type="pdf",
        )
    )

    assert result.ok is True
    assert result.data["file_key"] == "file_v2_test"
    assert result.data["request_payload"]["msg_type"] == "file"


def test_registry_exposes_feishu_media_tools():
    specs = {spec.name: spec for spec in tool_specs()}

    assert specs["feishu_send_image_message"].input_schema["required"] == ["receive_id", "image_path"]
    assert specs["feishu_send_file_message"].input_schema["required"] == ["receive_id", "file_path"]
