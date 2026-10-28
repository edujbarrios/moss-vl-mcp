# MOSS-VL MCP 👁️

**Give Claude Code, Codex, and other MCP-compatible agents visual understanding.** Use [MOSS-VL](https://github.com/OpenMOSS/MOSS-VL) to inspect screenshots, compare UI states, review test recordings, and observe visual changes over time.

This is an **unofficial Python MCP server**. Your coding agent still reasons, runs tests, and edits code; **MOSS-VL provides visual observations**.

> **Status: v0.1, experimental.** The MCP tools and mocked unit tests are implemented, but full GPU inference has **not** been verified end to end in this repository. Model weights are not included, and this MCP does not launch a GPU inference backend.

## What is it useful for? A practical example

Imagine a Playwright test passes, but the final screen shows a button hidden behind a modal. Logs and DOM assertions alone might miss that. With this MCP, your agent can **inspect a screenshot**, **compare it with an earlier state**, and connect the visual evidence to the relevant code.

**Workflow:** save a screenshot → call **inspect_ui** → check the suspected issue against the code → apply a fix → compare before/after screenshots with **compare_ui_states**.

These are model-generated observations, **not** deterministic pixel diffs or proof that a bug exists.

## Quick start (Python 3.11+)

Run these commands on the machine where Claude Code or Codex will launch the MCP:

~~~bash
git clone https://github.com/edujbarrios/moss-vl-mcp.git
cd moss-vl-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
mkdir -p "$HOME/moss-vl-media"
~~~

These examples use Bash on macOS/Linux. On Windows, activate the virtual environment using your shell and use the executable at .venv\Scripts\moss-vl-mcp.exe.

**Important:** the base installation is enough to register the MCP and check its prerequisites, **not** to run visual inference. A compatible inference backend is required for image, video, or realtime analysis.

### Connect to Claude Code

From the repository directory:

~~~bash
claude mcp add --scope user \
  --env MOSS_VL_MEDIA_ROOT="$HOME/moss-vl-media" \
  --transport stdio moss-vl -- "$PWD/.venv/bin/moss-vl-mcp"

claude mcp list
~~~

Start a new Claude Code session and run **/mcp** to inspect the connection and available tools.

### Connect to Codex

~~~bash
codex mcp add moss-vl \
  --env MOSS_VL_MEDIA_ROOT="$HOME/moss-vl-media" \
  -- "$PWD/.venv/bin/moss-vl-mcp"

codex mcp list
~~~

Restart the agent session after registration. Both commands point to the **locally installed virtual-environment executable**; this project does not assume a published PyPI package.

## Demo 1: check your setup without a GPU

Type this **in your agent's chat**, not in a terminal:

> Call the moss-vl MCP tool **check_moss_vl_setup**. Tell me which optional dependencies are detected, whether the media folder exists, and what I still need to analyze a screenshot. Do not load a model.

The tool checks the media folder, optional Python modules, and whether screen capture is enabled. It **does not** check GPU availability, checkpoint compatibility, actual inference, or realtime WebSocket connectivity. Installed dependencies are **not** proof that the model works.

## Demo 2: inspect a screenshot (offline model required)

**1. Prepare the inference environment.** Follow the [official MOSS-VL offline inference guide](https://github.com/OpenMOSS/MOSS-VL/tree/main/inference/offline) to configure a compatible checkpoint and GPU environment. Install this MCP's optional dependencies in that environment:

~~~bash
python -m pip install -e '.[offline]'
~~~

The default checkpoint is **OpenMOSS-Team/MOSS-VL-Instruct-0708**. To use a different checkpoint, set **MOSS_VL_CHECKPOINT** in the MCP client's environment configuration and restart the client. The model is loaded on the first visual analysis request.

**2. Place your screenshot inside the allowed media folder.**

~~~bash
cp /path/to/your/screenshot.png "$HOME/moss-vl-media/login.png"
~~~

**3. Ask your agent:**

> Use moss-vl **inspect_ui** on **login.png** in the configured media folder. Describe the layout, any overlapping elements, and visible error messages. Separate what you can see from hypotheses, then suggest what to verify in the source code.

**4. Verify a visual change.** Save two screenshots in the same folder as **before.png** and **after.png**. Then ask:

> Call **compare_ui_states** with **before.png** and **after.png**. Explain what changed, which visible changes might be regressions, and what cannot be determined from the images alone.

The MCP returns **visual observations**. The agent, automated tests, and human review must verify any suspected issue before considering it resolved.

## Demo 3: review a test recording

Save a Playwright recording under the configured media folder as **recording.mp4**. Ask your agent:

> Use moss-vl **analyze_test_recording** on **recording.mp4**. Summarize the visible steps in order, identify unexpected UI states, and point to relevant parts of the codebase to investigate. Do not invent events that are not shown.

Use **analyze_video** for general video questions, or **analyze_image** to describe an image without the UI-review prompt.

**This MCP does not run Playwright or record the test itself.** You or your coding agent must produce the media file first.

## Demo 4: watch visual changes in real time

Realtime observation requires a **separate** [MOSS-VL-Realtime reference server](https://github.com/OpenMOSS/MOSS-VL/blob/main/inference/realtime/README.md) running on a suitable GPU. From the **OpenMOSS/MOSS-VL** repository, for example:

~~~bash
CUDA_VISIBLE_DEVICES=0 python inference/realtime/run_online_inference.py \
  --serve --host 127.0.0.1 --port 8000
~~~

By default, the MCP connects to **ws://127.0.0.1:8000/v1/realtime**. Override this with **MOSS_VL_REALTIME_URL** in your MCP client configuration if needed. **SGLang-Omni uses a different protocol and is not supported by this integration.**

Screen capture records **the desktop of the machine hosting the MCP process**, not a remote user's screen. To opt in, install the optional dependencies:

~~~bash
python -m pip install -e '.[screen]'
~~~

Add **--env MOSS_VL_ALLOW_SCREEN_CAPTURE=1** to the Claude Code or Codex registration command, then restart the agent. Capture is disabled by default because the local screen may contain sensitive content.

Example prompt for the agent:

> Create a session with **start_visual_session**. Use **start_screen_observation** to observe monitor 1 at 1 FPS for 30 seconds. Use **ask_visual_session** to ask about unexpected changes, poll **get_visual_events** using its **next_seq** cursor, and stop both the observation and session when finished.

The agent must **poll** for results; there are no automatic push notifications. Screen capture is capped at **2 FPS and 5 minutes** per request. The reference realtime backend handles one active session per model process.

## Available MCP tools

| Use case | MCP tools | Requirements |
| --- | --- | --- |
| Check local setup | **check_moss_vl_setup** | Base installation |
| Understand images and videos | **analyze_image**, **analyze_video** | Offline model |
| Visual QA | **inspect_ui**, **compare_ui_states**, **analyze_test_recording** | Offline model |
| Realtime sessions | **start_visual_session**, **push_visual_frame**, **ask_visual_session**, **get_visual_events**, **stop_visual_session** | Realtime backend |
| Capture the local screen | **start_screen_observation**, **get_screen_observation_status**, **stop_screen_observation** | Realtime backend + screen extra + explicit opt-in |
| Replay video on the backend | **replay_visual_video**, **stop_visual_video** | Realtime backend + shared file path + **MOSS_VL_ALLOW_SERVER_VIDEO=1** |

**MOSS_VL_MEDIA_ROOT** restricts which local files the MCP can read. Relative paths and symlinks that escape the allowed directory are rejected. For server-side realtime video replay, the **same absolute path** must be accessible on both the MCP host and the inference-server host.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| MCP tools are missing | Run **claude mcp list** or **codex mcp list**, check the absolute executable path, and restart the agent. |
| Optional dependencies are missing | Call **check_moss_vl_setup**. The base install includes neither offline model dependencies nor screen-capture extras. |
| Image analysis fails | Verify the upstream checkpoint and dependencies in the GPU environment. The setup check does not validate model inference. |
| Media file is rejected | Move the file inside **MOSS_VL_MEDIA_ROOT**. Paths and symlinks that escape the directory are intentionally rejected. |
| Realtime session will not start | Check that the reference server is running and **MOSS_VL_REALTIME_URL** points to it. |
| No new realtime events appear | Send frames or start screen capture, ask a question via **ask_visual_session**, and poll **get_visual_events** using **next_seq**. |
| Screen capture does not work | Install **.[screen]**, explicitly enable capture, and grant operating-system screen-recording permissions. |

**Privacy and security:** use a dedicated, narrowly scoped media directory. Do not share screenshots containing passwords or other secrets. Never expose the reference WebSocket service publicly without TLS, authentication, and network restrictions.

## Development and credits

~~~bash
python -m pip install -e '.[dev]'
ruff check src tests
pytest -q
~~~

Tests use mocked backends. **End-to-end GPU inference validation is still pending.**

More resources: [detailed agent usage guide](docs/AGENT_USAGE.md) · [configuration example](.env.example) · [OpenMOSS project](https://github.com/OpenMOSS/MOSS-VL).

Created and maintained by [@edujbarrios](https://github.com/edujbarrios). This is an **independent, unofficial community project**, not affiliated with or endorsed by OpenMOSS. The models and original research belong to their respective authors. Review upstream model and dependency licenses before deployment.
