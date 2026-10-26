"""Offline adapter tests without downloading an 11B model."""

from contextlib import nullcontext
import sys
from types import SimpleNamespace

import pytest

from moss_vl_mcp.offline import OfflineVisionBackend


class FakeModel:
    def __init__(self):
        self.received = []

    def offline_batch_generate(self, processor, queries):
        self.received.append(queries)
        return {"results": [{"text": "A user opens the settings panel."}]}


@pytest.mark.asyncio
async def test_offline_adapter_reuses_loaded_model(monkeypatch):
    model = FakeModel()
    backend = OfflineVisionBackend("test-checkpoint")
    backend._model = model
    backend._processor = object()
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(inference_mode=lambda: nullcontext())
    )

    first = await backend.analyze("Describe it", images=["/tmp/example.png"])
    second = await backend.analyze("Summarize", videos=["/tmp/demo.mp4"])

    assert first == "A user opens the settings panel."
    assert second == first
    assert len(model.received) == 2
    assert model.received[0][0]["images"] == ["/tmp/example.png"]
    assert model.received[1][0]["videos"] == ["/tmp/demo.mp4"]


@pytest.mark.asyncio
async def test_offline_adapter_rejects_excessive_tokens():
    backend = OfflineVisionBackend("unused")
    with pytest.raises(ValueError, match="max_tokens"):
        await backend.analyze("question", max_tokens=999999)
