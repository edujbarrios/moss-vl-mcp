"""Lazy-loaded Transformers adapter (Adapter + Dependency Injection)."""

import asyncio
import threading
from typing import Any


class OfflineVisionBackend:
    """Load MOSS-VL only on first request; serialize GPU inference per process."""

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
        if not 1 <= max_tokens <= 2048:
            raise ValueError("max_tokens must be between 1 and 2048")
        with self._lock:
            self._ensure_model()
            import torch

            query = {
                "prompt": prompt,
                "images": images,
                "videos": videos,
                "generate_kwargs": {"max_new_tokens": max_tokens, "do_sample": False},
            }
            with torch.inference_mode():
                response = self._model.offline_batch_generate(self._processor, [query])
            return str(response["results"][0]["text"])

    async def analyze(
        self, prompt: str, *, images: list[str] | None = None,
        videos: list[str] | None = None, max_tokens: int = 512
    ) -> str:
        return await asyncio.to_thread(
            self._infer, prompt, images or [], videos or [], max_tokens
        )