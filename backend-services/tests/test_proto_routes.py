import io
import pytest


@pytest.mark.asyncio
async def test_proto_upload_and_get(monkeypatch, authed_client):
    import routes.proto_routes as pr
    # Fake protoc invocation to avoid dependency
    class _FakeCompleted:
        pass
    def _fake_run(*args, **kwargs):
        return _FakeCompleted()
    monkeypatch.setattr(pr.subprocess, "run", _fake_run)

    proto_content = b"""
        syntax = "proto3";
        message Hello { string name = 1; }
    """
    files = {"file": ("hello.proto", io.BytesIO(proto_content), "text/plain")}
    up = await authed_client.post("/platform/proto/myapi/v1", files=files)
    assert up.status_code in (200, 201)

    # Get back the proto content
    gp = await authed_client.get("/platform/proto/myapi/v1")
    assert gp.status_code == 200
    content = gp.json().get("content") or gp.json().get("response", {}).get("content")
    assert "syntax = \"proto3\";" in content

