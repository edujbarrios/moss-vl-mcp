# MOSS-VL MCP

**Give AI agents eyes — from images to continuous visual understanding.**

An **unofficial Python MCP server** that lets Claude Code, OpenAI Codex, and other MCP-compatible agents use [MOSS-VL](https://github.com/OpenMOSS/MOSS-VL) to understand images, recorded videos, and ongoing visual processes.

**Why?** Agents can write code and run tools, but they often cannot *observe what is happening over time*. This project aims to give them a reusable visual-perception layer: analyze a screenshot, follow a video stream, detect relevant changes, and use those observations in debugging and automation workflows.

> **Early development (v0.1).** MCP tools and unit tests are implemented, but end-to-end GPU inference is not yet verified. Not affiliated with or endorsed by OpenMOSS.

## What can agents do?

| Mode | MCP tools |
| --- | --- |
| **Images & video** | `analyze_image`, `analyze_video` |
| **Visual QA** | `inspect_ui`, `compare_ui_states`, `analyze_test_recording` |
| **Real-time observation** | `start_visual_session`, `push_visual_frame`, `ask_visual_session`, `get_visual_events`, `stop_visual_session` |
| **Live screen capture** | `start_screen_observation`, `get_screen_observation_status`, `stop_screen_observation` |
| **Video replay** | `replay_visual_video`, `stop_visual_video` |

Claude or Codex remains the **main agent**. MOSS-VL supplies visual understanding; the agent decides what to do with it.

## Quick start

**Requires Python 3.11+** and a suitable GPU/model environment for inference.

```bash
git clone https://github.com/edujbarrios/moss-vl-mcp.git
cd moss-vl-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Choose the backend you need:

- **Images / recorded videos:** follow [OpenMOSS offline setup](https://github.com/OpenMOSS/MOSS-VL/tree/main/inference/offline) and install `pip install -e '.[offline]'` in a compatible environment. Set `MOSS_VL_CHECKPOINT` to your checkpoint/model ID if needed. The model loads on first use.
- **Live video:** run the [official MOSS-VL-Realtime reference server](https://github.com/OpenMOSS/MOSS-VL/blob/main/inference/realtime/README.md) on a GPU. From the **upstream MOSS-VL checkout**:

  ```bash
  CUDA_VISIBLE_DEVICES=0 python inference/realtime/run_online_inference.py \
    --serve --host 127.0.0.1 --port 8000
  ```

  By default, this MCP connects to `ws://127.0.0.1:8000/v1/realtime`. **SGLang-Omni uses a different protocol and is not yet supported.**

### Connect to Claude Code

Replace `/absolute/path/to/...` with your real paths. The media root limits which local files agents can read.

```bash
claude mcp add --scope user \
  --env MOSS_VL_MEDIA_ROOT=/absolute/path/to/media \
  --transport stdio moss-vl -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp

claude mcp list
```

Open Claude Code and use `/mcp` to inspect the connection.

### Connect to Codex

```bash
codex mcp add moss-vl \
  --env MOSS_VL_MEDIA_ROOT=/absolute/path/to/media \
  -- /absolute/path/to/moss-vl-mcp/.venv/bin/moss-vl-mcp

codex mcp list
```

Restart the agent after registering the MCP. **The package is not on PyPI yet**; use your local virtualenv executable.

## Try it from your agent

Once the relevant model backend is available, ask Claude Code or Codex:

**Analyze an image**
> Use the moss-vl `analyze_image` tool on `/absolute/path/to/media/screen.png`. Describe the interface and identify visible issues.

**Analyze a video**
> Use `analyze_video` on `/absolute/path/to/media/demo.mp4` and summarize the sequence of actions.

**Debug a UI**
> Record my Playwright test under the configured media directory, use `analyze_test_recording` to inspect visual failures, correlate them with the code, fix the issue, and rerun the test.

**Watch a process live**
> Start a MOSS-VL realtime session, observe monitor 1 at 1 FPS for 60 seconds, ask about unexpected changes, poll `get_visual_events`, then stop observation and close the session.

For **screen capture**, first install `pip install -e '.[screen]'` and explicitly set `MOSS_VL_ALLOW_SCREEN_CAPTURE=1` in the MCP process. It captures the **MCP host's** desktop, not automatically a remote agent's screen. Capture is limited to 2 FPS and 5 minutes per request.

## Important notes

- The MCP **does not include model weights** or start a GPU inference server by itself.
- Real-time observations are read by **polling** `get_visual_events`; there are no automatic push alerts to the agent.
- Set `MOSS_VL_MEDIA_ROOT` to a narrow folder and only enable screen capture when you intend to share its contents.
- The reference realtime backend supports **one session per model process**. Visual findings can be wrong and should be verified.
- Remote upstream WebSockets require authentication/TLS at the deployment boundary; the reference service has no built-in auth.

**More details:** [Full agent setup and workflows](docs/AGENT_USAGE.md) · [Configuration example](.env.example) · [OpenMOSS project](https://github.com/OpenMOSS/MOSS-VL)

## Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest -q
```

Unit tests use mocked backends; GPU end-to-end validation is still pending.

## Credits

Created and maintained by [**@edujbarrios**](https://github.com/edujbarrios). This is an **independent, unofficial community project**, not affiliated with, sponsored by, endorsed by, or maintained by OpenMOSS. Credit for the MOSS-VL models, research, and original inference code belongs to the [OpenMOSS team](https://github.com/OpenMOSS/MOSS-VL). Check upstream model and dependency licenses before deploying.
