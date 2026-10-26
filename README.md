# MOSS-VL MCP

**Give AI Agents Eyes.** An unofficial community MCP integration for [OpenMOSS/MOSS-VL](https://github.com/OpenMOSS/MOSS-VL), by [@edujbarrios](https://github.com/edujbarrios).

> **Project status:** early development. This project is independent and is not affiliated with, endorsed by, or maintained by OpenMOSS.

## Why this MCP exists

AI coding and automation agents can inspect individual images, but often lack a reusable way to **observe how visual processes evolve over time**. This project aims to make MOSS-VL's understanding of screenshots, recorded video, and ongoing visual streams available as tools to MCP-compatible agents, including Claude Code and OpenAI Codex.

The goal goes beyond single-frame Q&A: an agent should be able to start an observation session, deliver timestamped frames, ask questions while new images arrive, collect relevant events, and combine those observations with coding, testing, or automation tools.

## Capabilities (first iteration)

| Capability | Tools | State |
| --- | --- | --- |
| Offline image and video understanding | `analyze_image`, `analyze_video` | Implemented adapter; requires upstream inference installation |
| Visual QA | `inspect_ui`, `analyze_test_recording` | Prompt-based tools; not an autonomous testing system |
| Live visual sessions | `start_visual_session`, `send_visual_frame`, `ask_visual_session`, `get_visual_events`, `stop_visual_session` | WebSocket adapter to official MOSS-VL-Realtime reference server |
| Capture screen/camera automatically | — | Planned; currently a producer must submit frames |
| Event subscriptions/push alerts | — | Planned; clients poll `get_visual_events` |

The reference WebSocket backend supports one session per model process. Use a separate process for each active session or a specialized multi-session backend with a separately implemented adapter.

## Install

Python 3.11+:

```bash
git clone https://github.com/edujbarrios/moss-vl-mcp.git
cd moss-vl-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

You also need to install and run the actual **MOSS-VL model/backend**. This Python package does not bundle model weights, GPUs, Transformers, or the OpenMOSS repository.

### Offline image/video backend

Install [OpenMOSS/MOSS-VL](https://github.com/OpenMOSS/MOSS-VL) and its inference dependencies in the Python environment that will invoke its script. Configure:

```bash
export MOSS_VL_MEDIA_ROOT=/absolute/path/to/allowed/media
export MOSS_VL_OFFLINE_SCRIPT=/absolute/path/to/MOSS-VL/inference/offline/run_inference.py
export MOSS_VL_CHECKPOINT=/absolute/path/to/MOSS-VL-Instruct-checkpoint
# Optional if the model environment is separate:
export MOSS_VL_PYTHON=/absolute/path/to/model-python
```

Each offline request runs the upstream script as a subprocess, which **reloads the model for every request**. This is an integration baseline, not an efficient production inference service. A persistent inference adapter is on the roadmap.

### Realtime backend

In an installation of the upstream repository with a compatible GPU:

```bash
CUDA_VISIBLE_DEVICES=0 python inference/realtime/run_online_inference.py --serve --host 127.0.0.1 --port 8000
```

Configure this MCP server:

```bash
export MOSS_VL_REALTIME_URL=ws://127.0.0.1:8000/v1/realtime
export MOSS_VL_MEDIA_ROOT=/absolute/path/to/allowed/media
```

The initial adapter targets only the upstream **reference WebSocket protocol** at `/v1/realtime`. SGLang-Omni's `/v1/video/realtime` and hosted MOSI's `/v1/realtime` use different protocols and **are not interchangeable**.

### Launch the MCP server

```bash
moss-vl-mcp
# or:
python -m moss_vl_mcp
```

The server uses MCP **stdio**, so tools such as Claude Code or Codex should launch it as a child process.

Claude Code, from the checkout directory:

```bash
claude mcp add moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp
```

Codex:

```bash
codex mcp add moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp
```

Ensure the model/backend environment variables are present in the spawned MCP process.

## Example agent workflows

- **Visual debugging:** have Playwright save a screenshot or video, inspect it through an MCP tool, then verify the proposed fix in code.
- **Ongoing observation:** start a visual session, feed it timestamped JPEG/PNG frames from a camera or screen-capture producer, send a question, and poll for output.
- **Recorded process analysis:** analyze a training or workflow video and ask for a chronological explanation of the observed actions.

MOSS-VL output can be incorrect; validate observations before taking consequential actions.

## Architecture

```text
MCP tools (server.py)
   |
   +-- VisualService -------- OfflineInference (Protocol)
   |                             +-- OfficialOfflineCLI
   +-- SessionManager ------- RealtimeSession (Protocol)
   |                             +-- ReferenceWebSocketSession
   +-- MediaGuard (explicit filesystem allowlist)
```

The model adapters are replaceable (Strategy / Ports & Adapters), sessions own their lifecycle, and filesystem access is restricted to `MOSS_VL_MEDIA_ROOT`. Remote media URLs are not accepted by MCP tools.

## Configuration

See `.env.example`. Environment variables are read when the process starts. Media paths must resolve inside the configured root. Only local files with supported extensions are accepted.

## Development

```bash
pytest -q
```

Tests use fakes and do not require model weights or a GPU. Integration with a real MOSS-VL checkpoint and video streams has not yet been verified.

## Roadmap

- Persistent offline model serving
- Screen/camera producer with explicit user consent and resource limits
- More advanced event filtering, semantic summaries, and visual memory
- SGLang-Omni multi-session adapter
- Playwright hooks and repeatable QA evaluations
- Security hardening and authenticated remote deployment

## Attribution / Disclaimer

Independent unofficial integration created and maintained by [@edujbarrios](https://github.com/edujbarrios). Not affiliated with, sponsored by, endorsed by, or maintained by [OpenMOSS](https://github.com/OpenMOSS/MOSS-VL). All credit for the original models, research, and inference implementations belongs to their respective authors. Check the licenses for model checkpoints and dependencies separately.
