# MOSS-VL MCP

**Give AI Agents Eyes — from static images to continuous visual understanding.**

Unofficial, community-maintained Python MCP server for [OpenMOSS/MOSS-VL](https://github.com/OpenMOSS/MOSS-VL), created by [@edujbarrios](https://github.com/edujbarrios). Not affiliated with or endorsed by the OpenMOSS team.

> **Early development (v0.1).** Tools are implemented, but have not yet been validated against a GPU-hosted MOSS-VL instance. Realtime support currently targets the upstream **reference** `/v1/realtime` WebSocket API, **not** SGLang-Omni's separate wire protocol.

## Why this MCP?

Agent workflows can read files and execute code, but often cannot continuously observe what changes on a screen or in a video. MOSS-VL MCP exposes visual perception as agent-accessible tools, allowing agents to **see** images, **understand** recordings, **observe** timestamped frame streams, **ask questions** during a session, and **react** using visual evidence combined with their existing tools.

The objective is not just `analyze_image`: it is to grow into a **persistent visual perception layer** for Claude Code, OpenAI Codex, and other MCP clients. A visual QA agent could record a test, identify a suspicious UI transition, correlate evidence with source code, and run the test again after a fix. The model provides observations; the coding agent remains responsible for actions and verification.

## Capabilities

| Module | MCP tools | Status |
| --- | --- | --- |
| Offline vision | `analyze_image`, `analyze_video` | Implemented, requires model/GPU |
| Visual QA | `inspect_ui`, `analyze_test_recording`, `compare_ui_states` | Prompt-based inference, not automated defect proof |
| Realtime | `start_visual_session`, `push_visual_frame`, `ask_visual_session`, `get_visual_events`, `stop_visual_session` | Implemented against upstream reference WebSocket |
| Realtime replay | `replay_visual_video`, `stop_visual_video` | Opt-in; path must exist on inference host |

The realtime backend can emit incremental outputs, acknowledgements and video lifecycle notifications. `get_visual_events(after_seq=...)` exposes a bounded event log for polling. It does **not** push spontaneous notifications into the MCP client; integrations must poll or orchestrate their own subscription loop.

## Architecture

```text
Claude Code / Codex / other MCP clients
                    |
               MCP / stdio
                    |
      src/moss_vl_mcp/server.py    (tool facade / composition root)
            /               \
     offline.py           realtime.py
   Transformers lazy      Session registry + WebSocket adapter
     inference                     |
          |               MOSS-VL reference realtime server
     MOSS-VL-Instruct       ws://127.0.0.1:8000/v1/realtime
```

Patterns: **Adapter** (separate backend contracts), **Dependency Injection** (testable server composition), **Factory** (per-session creation), and **Registry** (bounded session lifecycle). No model weights are included.

## Setup

Requires Python 3.11+ for the MCP adapter; upstream MOSS-VL recommends a Python 3.12 environment and compatible PyTorch/Transformers builds for model inference.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For local *offline* inference also install the optional dependencies, and follow [OpenMOSS's inference installation notes](https://github.com/OpenMOSS/MOSS-VL/tree/main/inference/offline). The model is loaded lazily on the first request and needs substantial GPU memory.

```bash
pip install -e '.[offline]'
```

For *realtime* inference, separately deploy the [official reference service](https://github.com/OpenMOSS/MOSS-VL/blob/main/inference/realtime/README.md) with its dependencies and GPU:

```bash
# In your MOSS-VL checkout / compatible model environment:
CUDA_VISIBLE_DEVICES=0 python inference/realtime/run_online_inference.py \
  --serve --host 127.0.0.1 --port 8000
```

Then configure this MCP process:

```bash
export MOSS_VL_MEDIA_ROOT="$HOME/videos"  # restrict which local files agents may read
export MOSS_VL_REALTIME_URL="ws://127.0.0.1:8000/v1/realtime"
export MOSS_VL_CHECKPOINT="OpenMOSS-Team/MOSS-VL-Instruct-0708"
moss-vl-mcp
```

### Claude Code

```bash
claude mcp add moss-vl -- uvx --from moss-vl-mcp moss-vl-mcp
```

For a local source checkout without a published package:

```bash
claude mcp add moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp
```

### OpenAI Codex

```bash
codex mcp add moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp
```

> The `uvx` package command will work only **after publication to a package index**. For now use the local checkout command. Client and inference service must share a filesystem for offline media paths. For realtime replay, the *inference host* must be able to read the path too.

## Configuration

| Environment variable | Default | Description |
| --- | --- | --- |
| `MOSS_VL_MEDIA_ROOT` | current working directory | Root allowed for local images and videos; rejects traversal and symlink escape |
| `MOSS_VL_CHECKPOINT` | `OpenMOSS-Team/MOSS-VL-Instruct-0708` | Offline model ID or checkpoint directory |
| `MOSS_VL_REALTIME_URL` | `ws://127.0.0.1:8000/v1/realtime` | Reference backend WebSocket endpoint |
| `MOSS_VL_MAX_SESSIONS` | `1` | Limit for concurrently tracked sessions (reference backend itself supports one) |
| `MOSS_VL_ALLOW_SERVER_VIDEO` | `0` | Set to `1` to allow replay of server-local video paths |

### Session workflow

1. `start_visual_session(prompt="Watch for UI changes")` → returns `session_id`.
2. `push_visual_frame(session_id, path="frames/001.jpg", timestamp=0.0)` → repeat with increasing timestamps; a separate capture process can produce the frames.
3. `ask_visual_session(session_id, prompt="What changed?")` → queues the follow-up question.
4. `get_visual_events(session_id, after_seq=0)` → read output and remember `latest_seq` to avoid duplicates.
5. `stop_visual_session(session_id)` → frees the model connection.

**Scope:** The MCP does not yet include continuous local camera/screen capture, browser hooks, proactive MCP notifications, or SGLang-Omni integration. These are roadmap items, not implemented features.

## Security & limitations

- Media access is restricted to `MOSS_VL_MEDIA_ROOT`; choose a narrow dedicated directory and avoid mounting secrets.
- Do not expose the upstream reference WebSocket directly to the internet: it has no built-in authentication. Use loopback or an authenticated TLS reverse proxy.
- `replay_visual_video` is disabled by default; the path is read on the inference host. Configure shared filesystems deliberately.
- Local media is sent to the inference backend when using realtime tools; ensure you trust that service.
- WebSocket output can contain MOSS-VL control tokens. Event history is volatile and limited to the latest 500 messages per session.
- Reference realtime serving supports one active session per model instance. Setting the MCP session limit higher does **not** increase backend capacity.
- Model-generated QA descriptions are hypotheses requiring verification, not guaranteed defect reports or safety signals.
- Inference loads third-party checkpoint code with `trust_remote_code=True`; use vetted checkpoints and isolated environments.

## Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest -q
```

Tests use fake inference adapters or WebSockets; they do not require GPU weights. CI runs lint and unit tests. End-to-end GPU tests are a future milestone.

## Roadmap

- [x] MCP tool registration, offline adapter, realtime WebSocket sessions, event polling
- [x] Visual QA prompts and initial unit tests
- [ ] GPU end-to-end verification against original MOSS-VL checkpoints
- [ ] Local screen/camera capture workers with bounded queues and consent controls
- [ ] Dedicated SGLang-Omni adapter and parallel stream support
- [ ] Temporal QA reports tied to evidence frames and Playwright traces
- [ ] Release to PyPI / MCP Registry

## Credits & disclaimer

**MOSS-VL MCP** is an independent, unofficial community project by [@edujbarrios](https://github.com/edujbarrios). It is **not affiliated with, endorsed by, sponsored by, or maintained by OpenMOSS**. Original models, inference code and research belong to the [OpenMOSS team](https://github.com/OpenMOSS/MOSS-VL) and their contributors. Consult upstream licenses and each model checkpoint's terms before deployment.