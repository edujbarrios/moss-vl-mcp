"""Offline adapter contract tests; no GPU or model weights required."""

import sys
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from moss_vl_mcp.offline import OfflineVisionBackend, build_multimodal_query


class FakeModel:
    def __init__(self):
        self.received = []

    def offline_batch_generate(self, processor, queries):
        self.received.append(queries)
        return {"results": [{"text": "A user opens the settings panel."}]}


def test_multimodal_query_schema_for_two_images():
    query = build_multimodal_query("Compare UI", ["before.png", "after.png"], [], 128)
    assert query == {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": "before.png"},
                    {"type": "image", "image": "after.png"},
                    {"type": "text", "text": "Compare UI"},
                ],
            }
        ],
        "generate_kwargs": {"max_new_tokens": 128, "do_sample": False},
    }


@pytest.mark.parametrize("prompt,tokens", [("", 256), ("   ", 256), ("hello", 0), ("hello", 2049)])
def test_build_query_validation(prompt, tokens):
    with pytest.raises(ValueError):
        build_multimodal_query(prompt, [], [], tokens)


@pytest.mark.asyncio
async def test_offline_adapter_reuses_loaded_model(monkeypatch):
    model = FakeModel()
    backend = OfflineVisionBackend("test-checkpoint")
    backend._model = model
    backend._processor = object()
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))

    first = await backend.analyze("Describe it", images=["/tmp/example.png"])
    second = await backend.analyze("Summarize", videos=["/tmp/demo.mp4"])

    assert first == "A user opens the settings panel."
    assert second == first
    assert len(model.received) == 2
    assert model.received[0][0]["messages"][0]["content"][0] == {
        "type": "image",
        "image": "/tmp/example.png",
    }
    assert model.received[1][0]["messages"][0]["content"][0] == {
        "type": "video",
        "video": "/tmp/demo.mp4",
    }


@pytest.mark.asyncio
async def test_offline_adapter_rejects_excessive_tokens():
    backend = OfflineVisionBackend("unused")
    with pytest.raises(ValueError, match="max_tokens"):
        await backend.analyze("question", max_tokens=999999)
