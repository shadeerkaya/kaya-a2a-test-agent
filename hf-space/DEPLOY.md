# Deploying the A2A test agent

Two paths. Both are free; each has one manual step I could not do for you.

## Current state

* GitHub repo (source of truth): <https://github.com/shadeerkaya/kaya-a2a-test-agent>
* HF Space created and files uploaded: <https://huggingface.co/spaces/shadeer/kaya-a2a-test-agent>
  * `A2A_TOKEN` secret set
  * **Blocked:** the Space was provisioned on **ZeroGPU** hardware, which requires a
    `@spaces.GPU`-decorated function. This is a CPU-only app, so HF reports
    `RUNTIME_ERROR: No @spaces.GPU function detected during startup`.
    The hardware selector kept reporting `requested: zero-a10g` and would not switch.

## Path A -- fix the HF Space (free, ~2 min)

1. Open <https://huggingface.co/spaces/shadeer/kaya-a2a-test-agent/settings>
2. Under **Space Hardware**, click **CPU basic** (2 vCPU / 16 GB, Free)
3. Click **Confirm new hardware**, and re-check the page shows CPU basic afterwards
   (the switch silently no-ops while the Space sits in RUNTIME_ERROR -- if it does,
   hit **Factory rebuild** on the same page first, then set the hardware)
4. Wait for the Space to reach **Running**
5. Verify:

```bash
BASE=https://shadeer-kaya-a2a-test-agent.hf.space \
  TOKEN=<the A2A_TOKEN from Settings -> Variables and secrets> \
  bash acceptance.sh     # expect: 13 passed, 0 failed
```

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
