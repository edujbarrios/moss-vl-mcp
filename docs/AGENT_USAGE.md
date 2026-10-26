# Using MOSS-VL MCP with Claude Code and OpenAI Codex

**MOSS-VL MCP is a tool server, not a replacement language model.** Claude Code or Codex remain the agent deciding what to do. When needed, they call MOSS-VL MCP tools to inspect images, analyze recorded video, or maintain a realtime visual session. The actual MOSS-VL model runs on a suitable GPU/backend; the MCP server only connects those capabilities to the agent.

> Unofficial community integration by [@edujbarrios](https://github.com/edujbarrios), not endorsed by or affiliated with OpenMOSS. All workflows described here require their corresponding backend to be configured. GPU end-to-end verification is still pending.

## 1. Install the server locally

Run from the machine where Claude Code / Codex will launch the MCP:

```bash
git clone https://github.com/edujbarrios/moss-vl-mcp.git
cd moss-vl-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[screen]'
mkdir -p "$HOME/moss-vl-media"
```

The `screen` extra enables optional **local** desktop capture; it does not install or run the vision model. For image and recorded-video inference on this machine, install the upstream MOSS-VL dependencies and the `offline` extra in a compatible GPU environment (follow the official upstream installation instructions).

Identify these absolute paths:

- **MCP executable:** `/absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp`
- **Media root:** `/absolute/path/to/media` — the only directory from which media files may be read.
- **Realtime endpoint (optional):** `ws://127.0.0.1:8000/v1/realtime`, running the original OpenMOSS reference server.

On Windows, the virtual-environment executable is typically `.venv\Scripts\moss-vl-mcp.exe`, and screen-capture support requires a desktop session. The commands below use a Unix shell.

**Choose the backend you need:**

- **Images / finished videos:** configure an MOSS-VL Instruct checkpoint in the MCP's Python environment. These tools load the model lazily.
- **Continuous observation:** run the upstream MOSS-VL-Realtime reference server separately on a GPU and configure `MOSS_VL_REALTIME_URL`. The MCP itself can run on a different machine only if networking and file/capture placement are understood.
- **Both:** set up both backends. Merely installing this repository does not install model weights or start an inference server.

## 2. Register in Claude Code

Replace both absolute paths before running:

```bash
claude mcp add --scope user \
  --env MOSS_VL_MEDIA_ROOT=/absolute/path/to/media \
  --env MOSS_VL_REALTIME_URL=ws://127.0.0.1:8000/v1/realtime \
  --transport stdio moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp

claude mcp list
```

To analyze **images or videos** with a specific checkpoint, add another `--env MOSS_VL_CHECKPOINT=/absolute/path/to/checkpoint` (or an upstream-supported model ID) before `moss-vl`. This model must be usable by the Python process launching the MCP.

For optional desktop capture add `--env MOSS_VL_ALLOW_SCREEN_CAPTURE=1` deliberately. **It can capture sensitive information shown on that machine.** Do not enable it automatically or in shared environments.

Start a new Claude Code conversation, run `/mcp` to inspect the connection and enabled tools, then describe what you want observed.

Claude's default `local` scope is tied to the current project; this example uses `user` scope so the MCP can be used across local projects. Avoid committing machine-specific paths or permissions to a shared `.mcp.json`.

## 3. Register in OpenAI Codex

```bash
codex mcp add moss-vl \
  --env MOSS_VL_MEDIA_ROOT=/absolute/path/to/media \
  --env MOSS_VL_REALTIME_URL=ws://127.0.0.1:8000/v1/realtime \
  -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp

codex mcp list
```

The MCP configuration is shared by the Codex CLI and compatible IDE integrations. For offline inference, optionally add `--env MOSS_VL_CHECKPOINT=/absolute/path/to/checkpoint`. For explicit local capture opt-in, add `--env MOSS_VL_ALLOW_SCREEN_CAPTURE=1` before `--`.

Restart the Codex session after adding or editing an MCP server so the tool list refreshes.

Alternative: register the stdio command in `~/.codex/config.toml`:

```toml
[mcp_servers.moss-vl]
command = "/absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp"

[mcp_servers.moss-vl.env]
MOSS_VL_MEDIA_ROOT = "/absolute/path/to/media"
MOSS_VL_REALTIME_URL = "ws://127.0.0.1:8000/v1/realtime"
# Optional:
# MOSS_VL_CHECKPOINT = "/absolute/path/to/checkpoint"
# MOSS_VL_ALLOW_SCREEN_CAPTURE = "1"
```

**No public PyPI package has been assumed.** Install this repository locally and point both clients at its executable; do not use `uvx --from moss-vl-mcp` until the package is actually published.

## 4. Talk to the agent — example prompts

These are prompts to type **inside Claude Code or Codex**. The agent discovers and calls the named MCP tools; you do not need to call them yourself from Python.

### A. Understand a screenshot (offline model)

> Use the MOSS-VL MCP tool `analyze_image` on `/absolute/path/to/media/checkout.png`. Describe the current state of the checkout screen and tell me which visible elements suggest the flow failed. Separate observations from assumptions.

### B. Summarize a recorded video (offline model)

> Use `analyze_video` from moss-vl on `/absolute/path/to/media/checkout-demo.mp4`. Explain the actions in temporal order, noting approximate times where possible. Do not invent hidden operations.

### C. Visual QA with a coding agent

> Run my Playwright signup flow and save the recording under `MOSS_VL_MEDIA_ROOT`. Call `analyze_test_recording` on that recording, correlate suspected visual issues with the app source code, implement a focused fix, rerun the test, and report what the new recording actually shows.

For before/after screenshots, ask the agent to invoke `compare_ui_states(before_path, after_path)`. It is a model-based comparison, **not** a deterministic screenshot diff. No test execution or automatic code changes are performed by the MCP itself.

### D. Observe a screen for one minute (realtime model)

Start the reference MOSS-VL-Realtime WebSocket server and explicitly enable screen capture first. Then tell Claude Code / Codex:

> Use moss-vl to create a realtime visual session about my UI test. Start `start_screen_observation` on monitor 1 at 1 FPS for 60 seconds. Ask the visual session to identify changes in the login interface, collect `get_visual_events` results using the `next_seq` cursor without skipping pages, summarize the evidence, and stop both the screen observer and the session.

Tool sequence:

```text
start_visual_session(prompt="Watch for UI failures")
  -> session_id
start_screen_observation(session_id, monitor_index=1, fps=1, duration_seconds=60)
ask_visual_session(session_id, prompt="Describe unexpected state changes")
get_visual_events(session_id, after_seq=0)
  -> save next_seq; call again if has_more or after new frames arrive
get_screen_observation_status(session_id)
stop_screen_observation(session_id)
stop_visual_session(session_id)
```

Screen capture occurs on **the machine hosting the MCP process**, not on a remote IDE user desktop. The MCP client does **not** receive automatic push notifications: an agent must poll events to learn what happened. A chat agent will not monitor indefinitely after its turn ends unless a separate orchestrator runs it.

### E. Send selected frames instead of capturing a screen (realtime model)

With a realtime session open, the agent can call `push_visual_frame(session_id, path="frames/0001.jpg", timestamp=0.0)`, followed by more frames in non-decreasing timestamp order. All images must be beneath `MOSS_VL_MEDIA_ROOT`.

### F. Replay a file as a realtime stream (reference server)

Only if the same absolute video path is readable **both on the MCP host and on the inference server host**, set `MOSS_VL_ALLOW_SERVER_VIDEO=1`. The agent can then call `replay_visual_video`, `ask_visual_session`, `get_visual_events`, and `stop_visual_video`. This is different from the offline `analyze_video` tool.

## 5. How it works

```text
Claude Code / Codex (reasoning, code changes, orchestration)
          |
      MCP tools (stdio)
          |
    moss-vl-mcp (Python)
          |                           |
   Offline inference            Realtime sessions
   MOSS-VL-Instruct             WS /v1/realtime
   images and videos            frames, prompts, events
                                      ^
                               screen/frame producer
```

The model does not take control of the operating system by itself. A coding agent decides when to read evidence, run tests, edit code, and verify outcomes. Treat model descriptions as hypotheses requiring checks.

## 6. Troubleshooting

| Symptom | What to check |
| --- | --- |
| MCP tools do not appear | Verify `claude mcp list` or `codex mcp list`, restart the agent, and use the **absolute** virtualenv executable path. |
| MCP connects but image/video analysis fails | Install official GPU inference dependencies and configure a valid `MOSS_VL_CHECKPOINT`. The first request loads the checkpoint. |
| `Media must be inside MOSS_VL_MEDIA_ROOT` | Place the file inside the configured directory; symlink escapes are deliberately rejected. |
| Realtime session cannot start | The official reference WebSocket service must be running and reachable at `MOSS_VL_REALTIME_URL`. |
| Screen observation disabled | Install `.[screen]`, set `MOSS_VL_ALLOW_SCREEN_CAPTURE=1`, and restart the MCP. |
| Screen capture fails in a container/headless session | Capture requires access to an actual local display, including permissions granted by the operating system. |
| No new realtime analysis appears | Ensure frames are arriving, send a question with `ask_visual_session`, and poll `get_visual_events` using `next_seq`. |
| Too many sessions | The upstream reference server supports **one active session per model process**. Close the active session first. |

Do not expose the unauthenticated upstream WebSocket publicly. Secure remote deployments with TLS, authentication and network restrictions.
