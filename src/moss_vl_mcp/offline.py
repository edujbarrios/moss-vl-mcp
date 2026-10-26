"""Lazy-loaded Transformers adapter (Adapter + Dependency Injection).

The upstream offline_batch_generate API consumes normalized multimodal messages,
not the convenience prompt/images/videos records used by its CLI sample loader.
"""

import asyncio
import threading
from typing import Any


def build_multimodal_query(
    prompt: str,
    images: list[str],
    videos: list[str],
    max_tokens: int,
) -> dict[str, Any]:
    """Create a query compatible with OpenMOSS's offline_batch_generate API."""
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    if not 1 <= max_tokens <= 2048:
        raise ValueError("max_tokens must be between 1 and 2048")

    content: list[dict[str, str]] = [
        *({"type": "image", "image": path} for path in images),
        *({"type": "video", "video": path} for path in videos),
        {"type": "text", "text": prompt},
    ]
    return {
        "messages": [{"role": "user", "content": content}],
        "generate_kwargs": {"max_new_tokens": max_tokens, "do_sample": False},
    }


class OfflineVisionBackend:
    """Load MOSS-VL on first request and serialize GPU inference per process."""

    def __init__(self, checkpoint: str) -> None:
        self.checkpoint = checkpoint
        self._model: Any = None
        self._processor: Any = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Offline inference needs model dependencies: pip install 'moss-vl-mcp[offline]' "
                "and follow the upstream checkpoint's PyTorch/Transformers installation notes"
            ) from exc

        self._processor = AutoProcessor.from_pretrained(
            self.checkpoint, trust_remote_code=True
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.checkpoint,
            trust_remote_code=True,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            attn_implementation="eager",
        ).eval()

    def _infer(self, prompt: str, images: list[str], videos: list[str], max_tokens: int) -> str:
        # Validate before allocating/loading GPU resources.
        query = build_multimodal_query(prompt, images, videos, max_tokens)
        with self._lock:
            self._ensure_model()
            import torch

            with torch.inference_mode():
                response = self._model.offline_batch_generate(self._processor, [query])
            try:
                text = response["results"][0]["text"]
            except (TypeError, KeyError, IndexError) as exc:
                raise RuntimeError("MOSS-VL returned an unexpected response format") from exc
            return str(text)

    async def analyze(
        self,
        prompt: str,
        *,
        images: list[str] | None = None,
        videos: list[str] | None = None,
        max_tokens: int = 512,
    ) -> str:
        return await asyncio.to_thread(
            self._infer, prompt, images or [], videos or [], max_tokens
        )
