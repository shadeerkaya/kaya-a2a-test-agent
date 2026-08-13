# Deploying the A2A test agent

Two paths. Both are free; each has one manual step I could not do for you.

## Current state — LIVE

* GitHub repo: <https://github.com/shadeerkaya/kaya-a2a-test-agent>
* **Deployed: <https://shadeer-kaya-a2a-test-agent.hf.space>** — 13/13 acceptance passing
  against the live URL.

| | Card URL (GET, authoring) | Endpoint (POST, execution) | Auth |
|---|---|---|---|
| Open | `https://shadeer-kaya-a2a-test-agent.hf.space/open/.well-known/agent-card.json` | `.../open/` | none |
| Secure | `https://shadeer-kaya-a2a-test-agent.hf.space/secure/.well-known/agent-card.json` | `.../secure/` | Bearer `$A2A_TOKEN` |

Re-verify any time:

```bash
BASE=https://shadeer-kaya-a2a-test-agent.hf.space \
  TOKEN=<A2A_TOKEN from Space Settings -> Variables and secrets> \
  bash acceptance.sh     # expect: 13 passed, 0 failed
```

### The ZeroGPU trap, and the fix that shipped

The Space was provisioned on **ZeroGPU** hardware, which aborts startup with
`No @spaces.GPU function detected during startup` unless the app declares such a
function. The build log gives it away: HF injects `torch` and `spaces==0.51.1`
into the image on ZeroGPU, which a CPU-only app never asks for.

Switching hardware to CPU basic in the UI would also fix it, but the setting would
not persist while the Space sat in `RUNTIME_ERROR`. So `app.py` instead declares a
no-op `@spaces.GPU` probe guarded by `try: import spaces / except ImportError`, so
it satisfies ZeroGPU and is skipped entirely on CPU hardware. That runs anywhere.

## Path B -- Render (needs a card, no Gradio layer)

Render requires credit-card verification even on the Free instance type ($1 temporary
authorization, not a charge). If that is acceptable, it is the better host: no Gradio
wrapper, faster cold start, and `render.yaml` in the repo root configures everything.

1. <https://dashboard.render.com/> -> sign in with GitHub
2. **New +** -> **Web Service** -> **Public Git Repository**
3. Paste `https://github.com/shadeerkaya/kaya-a2a-test-agent`
4. Instance type: **Free**. Add env var `A2A_TOKEN` (use the **Generate** button)
5. **Deploy Web Service**, then verify with `acceptance.sh` as above

No `PUBLIC_BASE_URL` needed -- `a2a_agent.py` reads `RENDER_EXTERNAL_URL`.

## Why the Gradio wrapper exists at all

HF's **Docker** SDK is a paid feature on this account, so the Space uses the free
**Gradio** SDK. Gradio runs on FastAPI, so `app.py` mounts the A2A sub-apps onto the
server Gradio binds. Two traps, both hit and fixed:

* calling `uvicorn.run()` ourselves -> `[Errno 98] address already in use`
* building the app without blocking -> exit code 0, reported as a runtime error
* Gradio 6 also fronts Python with a Node SSR proxy, so `ssr_mode=False` is required
  for the mounted routes to be reachable

On Render none of this applies -- it runs `Dockerfile` and `a2a_agent.py` directly.
