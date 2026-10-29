import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
import pytest

from astrophotoflow.contracts.software import SirilPreviewRequest
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.workflows import siril_preview


def test_live_preview_cancels_old_generation_and_releases_samples(tmp_path, monkeypatch):
    consumer = uuid4()
    body = SirilPreviewRequest(reference={"kind": "asset_version", "asset_version_id": uuid4(), "selection": {"kind": "whole_file"}},
                              member_index=0, consumer_id=consumer, generation=1, linked=True, shadowsclip=0, targetbg=0)
    released, requests = [], []
    first_started = asyncio.Event()

    def sample(_database, _settings, _cache, request, checkpoint):
        checkpoint()
        return SimpleNamespace(path=tmp_path / "linear.fit", folder=tmp_path,
                               close=lambda error: released.append((request.generation, error)))

    async def run(_settings, source, directory, parameters):
        requests.append((source, parameters.shadowsclip, parameters.targetbg))
        if parameters.generation == 1:
            first_started.set()
            await asyncio.Event().wait()
        return directory / "result.fit"

    monkeypatch.setattr(siril_preview, "prepare_siril_sample", sample)
    monkeypatch.setattr(siril_preview, "preview_autostretch", run)
    monkeypatch.setattr(siril_preview, "direct_fits_image", lambda *_args: Image.new("RGB", (12, 9), "blue"))

    class Cache:
        def write(self, path, content):
            path.write_bytes(content)

    async def scenario(executor):
        manager = siril_preview.SirilPreviews(None, SimpleNamespace(preview_workers=1), executor, Cache())
        first = asyncio.create_task(manager.render(body))
        await first_started.wait()
        newer = body.model_copy(update={"generation": 2, "targetbg": 0.25})
        result = await manager.render(newer)
        await asyncio.gather(first, return_exceptions=True)
        assert result.startswith(b"\x89PNG")
        assert requests == [(tmp_path / "linear.fit", 0, 0), (tmp_path / "linear.fit", 0, 0.25)]
        assert [item[0] for item in released] == [1, 2]
        with pytest.raises(ApiError) as stale:
            await manager.render(body)
        assert stale.value.code == "STALE_VIEW"
        await manager.cancel(consumer)
        assert not manager.active

    with ThreadPoolExecutor(max_workers=1) as executor:
        asyncio.run(scenario(executor))


def test_preview_http_is_authenticated_and_does_not_accept_source_paths(tmp_path, monkeypatch):
    import httpx
    from astrophotoflow.core.config import Settings
    from astrophotoflow.interfaces.http.app import create_app

    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, "token")
    monkeypatch.setattr(siril_preview, "get_package", lambda *_args: SimpleNamespace(availability="ready"))

    async def render(_body):
        return b"\x89PNGpreview"

    app.state.siril_previews = SimpleNamespace(start=lambda body: asyncio.create_task(render(body)))
    body = {"reference": {"kind": "asset_version", "asset_version_id": str(uuid4()), "selection": {"kind": "whole_file"}},
            "consumer_id": str(uuid4()), "generation": 1, "linked": True, "targetbg": 0, "shadowsclip": 0}

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = "/api/v1/software/packages/siril/autostretch-preview"
            assert (await client.post(path, json=body)).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (await client.post(path, json={**body, "path": "C:/arbitrary.fit"}, headers=headers)).status_code == 422
            result = await client.post(path, json=body, headers=headers)
            assert result.status_code == 200 and result.headers["content-type"] == "image/png"
            assert result.content == b"\x89PNGpreview"

    try:
        asyncio.run(scenario())
    finally:
        app.state.database.close()
