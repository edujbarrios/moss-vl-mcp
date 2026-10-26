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
| Continuous screen capture | `start_screen_observation`, `get_screen_observation_status`, `stop_screen_observation` | Opt-in; local display capture using optional `mss` / Pillow |

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
                             ^
                         capture.py (optional local screen producer)
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

## Use MOSS-VL inside Claude Code or Codex

**The agent remains Claude or Codex. MOSS-VL runs as a visual-perception backend accessed through MCP tools.** Installing the MCP does not download model weights or start GPU inference.

For a complete hands-on walkthrough (including model prerequisites, recorded-video workflows, visual QA, realtime observation, monitoring prompts, troubleshooting, and permissions), see **[Agent Usage Guide](docs/AGENT_USAGE.md)**.

### 1. Add the MCP to Claude Code

Clone and install this repository locally, then point Claude at the virtualenv executable. **Replace all example absolute paths**:

```bash
claude mcp add --transport stdio --scope user \
  --env MOSS_VL_MEDIA_ROOT=/absolute/path/to/media \
  --env MOSS_VL_REALTIME_URL=ws://127.0.0.1:8000/v1/realtime \
  moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp

claude mcp list
```

Launch Claude Code and use `/mcp` to verify that `moss-vl` is connected. Offline tools require the MOSS-VL-Instruct model to be available in the MCP's environment. Realtime tools require the official reference MOSS-VL-Realtime WebSocket service to be running. You can pass `--env MOSS_VL_CHECKPOINT=/absolute/path/to/checkpoint` when registering if needed.

### 2. Add the MCP to OpenAI Codex

```bash
codex mcp add moss-vl \
  --env MOSS_VL_MEDIA_ROOT=/absolute/path/to/media \
  --env MOSS_VL_REALTIME_URL=ws://127.0.0.1:8000/v1/realtime \
  -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp

codex mcp list
```

Restart Codex after configuring the MCP. Codex CLI and its IDE integration share MCP configuration. Alternatively, use `~/.codex/config.toml` as shown in the [Agent Usage Guide](docs/AGENT_USAGE.md).

**The package is not published to PyPI yet.** Do not use `uvx --from moss-vl-mcp` until a release is actually published. Use your local checkout.

### 3. Ask the agent to use the visual tools

Once connected, give Claude Code or Codex prompts like these:

**Analyze a screenshot (offline inference):**

> Use the `moss-vl` MCP `analyze_image` tool to inspect `/absolute/path/to/media/checkout.png`. Explain the visible UI state and flag any suspected error, separating evidence from assumptions.

**Analyze a video (offline inference):**

> Use `analyze_video` on `/absolute/path/to/media/demo.mp4`. Summarize what happens chronologically and identify important transitions.

**Visual QA (offline inference + agent coding tools):**

> Run the signup Playwright test, save its recording inside `MOSS_VL_MEDIA_ROOT`, and inspect it with `analyze_test_recording`. Correlate any visible issues with the source code, make a focused fix, and rerun the test to verify.

**Observe a live process (realtime backend + explicit opt-in capture):**

> Start a MOSS-VL realtime visual session, observe monitor 1 at 1 FPS for 60 seconds with `start_screen_observation`, ask about unexpected UI changes, poll `get_visual_events` using `next_seq`, and then stop both observation and session.

The realtime screen prompt **requires** `MOSS_VL_ALLOW_SCREEN_CAPTURE=1` and the optional `.[screen]` dependencies. Capture runs on the MCP server host (not automatically a remote client desktop), and can expose sensitive screen content. The MCP does not push alerts or run a coding agent in the background; the agent must retrieve events during its execution.

### How agents use the tools

```text
Claude Code / Codex -> MCP server -> MOSS-VL-Instruct (images, recordings)
                               \\-> MOSS-VL-Realtime (frames + prompts + events)
```

The agent chooses when to call the tools, reasons over their results, and performs any code changes using **its own** tools. MOSS-VL supplies visual evidence; it does not edit code or control the desktop by itself.

## Configuration

| Environment variable | Default | Description |
| --- | --- | --- |
| `MOSS_VL_MEDIA_ROOT` | current working directory | Root allowed for local images and videos; rejects traversal and symlink escape |
| `MOSS_VL_CHECKPOINT` | `OpenMOSS-Team/MOSS-VL-Instruct-0708` | Offline model ID or checkpoint directory |
| `MOSS_VL_REALTIME_URL` | `ws://127.0.0.1:8000/v1/realtime` | Reference backend WebSocket endpoint |
| `MOSS_VL_MAX_SESSIONS` | `1` | Limit for concurrently tracked sessions (reference backend itself supports one) |
| `MOSS_VL_ALLOW_SERVER_VIDEO` | `0` | Set to `1` to allow replay of server-local video paths |
| `MOSS_VL_ALLOW_SCREEN_CAPTURE` | `0` | Set to `1` to allow opt-in capture of the MCP host's screens (max 2 FPS, 5 minutes per request) |

### Session workflow (for agent orchestration)

1. `start_visual_session(prompt="Watch for UI changes")` → returns `session_id`.
2. `push_visual_frame(session_id, path="frames/001.jpg", timestamp=0.0)` → repeat with increasing timestamps; a separate capture process can produce the frames.
3. `ask_visual_session(session_id, prompt="What changed?")` → queues the follow-up question.
4. `get_visual_events(session_id, after_seq=0)` → read output and remember `next_seq` to page through the event log without skipping messages.
5. `stop_visual_session(session_id)` → frees the model connection.

### Optional continuous screen observation

This feature captures the screen of the **machine running the MCP server**, not automatically the desktop of a remote Claude/Codex client. It is **disabled by default** because a screen can contain passwords, private messages, and other sensitive information. Enable it only on a computer you control and for sessions you explicitly intend to observe:

```bash
pip install -e '.[screen]'
export MOSS_VL_ALLOW_SCREEN_CAPTURE=1
moss-vl-mcp
```

Start a realtime model session, then call:

1. `start_visual_session(prompt="Describe significant UI changes")`
2. `start_screen_observation(session_id, monitor_index=1, fps=1.0, duration_seconds=60)`
3. `get_screen_observation_status(session_id)` and `get_visual_events(session_id, after_seq=0)` periodically
4. `stop_screen_observation(session_id)` and `stop_visual_session(session_id)`

Screen frames are compressed as JPEG and transmitted directly to the configured Realtime WebSocket; this producer does not save screenshots to disk. One producer can run per session, limited to **2 FPS** and **300 seconds** per call. Frame capture is asynchronous while the MCP process remains alive, but visual events must be polled by the agent.

**Scope:** Camera capture, browser hooks, proactive MCP notifications, and SGLang-Omni integration are not implemented yet. They remain roadmap items.

## Security & limitations

- Media access is restricted to `MOSS_VL_MEDIA_ROOT`; choose a narrow dedicated directory and avoid mounting secrets.
- Do not expose the upstream reference WebSocket directly to the internet: it has no built-in authentication. Use loopback or an authenticated TLS reverse proxy.
- `replay_visual_video` is disabled by default; the path is read on the inference host. Configure shared filesystems deliberately.
- Screen capture is also disabled by default. It can capture private data on the MCP host: review the screen, enable it deliberately, and stop observation when no longer needed.
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
- [x] Optional local screen capture with explicit opt-in and bounded duration/FPS
- [ ] Camera capture, user-level consent UI, and end-to-end producer reliability tests
- [ ] Dedicated SGLang-Omni adapter and parallel stream support
- [ ] Temporal QA reports tied to evidence frames and Playwright traces
- [ ] Release to PyPI / MCP Registry

## Credits & disclaimer

**MOSS-VL MCP** is an independent, unofficial community project by [@edujbarrios](https://github.com/edujbarrios). It is **not affiliated with, endorsed by, sponsored by, or maintained by OpenMOSS**. Original models, inference code and research belong to the [OpenMOSS team](https://github.com/OpenMOSS/MOSS-VL) and their contributors. Consult upstream licenses and each model checkpoint's terms before deployment.