"""Hugging Face Spaces (Gradio SDK) entrypoint.

The HF Docker SDK is paid; the Gradio SDK is free. On the Gradio SDK, HF's runner
launches the Gradio server itself on 7860, so this script must NOT bind a port:
  * calling uvicorn.run() -> "[Errno 98] address already in use"
  * building an app and exiting -> exit code 0, reported as a runtime error

Gradio's internal server is a FastAPI subclass, so the A2A app is mounted onto it
after launch. `demo` stays a plain Blocks for HF to pick up.
"""
import gradio as gr

from a2a_agent import BASE, app as a2a_app

# HF provisions some Spaces on ZeroGPU, which aborts startup with
# "No @spaces.GPU function detected during startup" unless the app declares one.
# This agent is CPU-only, so declare a no-op purely to satisfy that check. On
# CPU hardware `spaces` is not installed and this is skipped entirely.
try:
    import spaces

    @spaces.GPU(duration=1)
    def _zerogpu_probe() -> str:
        """Never called. Present only so ZeroGPU startup validation passes."""
        return "ok"

except ImportError:
    pass

with gr.Blocks(title="KAYA A2A Test Agent") as demo:
    gr.Markdown(
        f"""
# KAYA A2A Test Agent

A2A **v0.3** agent for testing the KAYA External Agent node (REQ-0230).

| | Card URL (GET) | Endpoint (POST) | Auth |
|---|---|---|---|
| Open | `{BASE}/open/.well-known/agent-card.json` | `{BASE}/open/` | none |
| Secure | `{BASE}/secure/.well-known/agent-card.json` | `{BASE}/secure/` | Bearer |

Skills: `echo`, `slow_echo` (send text containing "slow" to stream progress).
"""
    )


def _attach_a2a(blocks: gr.Blocks) -> None:
    """Mount the A2A app onto whatever FastAPI server Gradio ends up using."""
    server_app = getattr(blocks, "server_app", None) or getattr(blocks, "app", None)
    if server_app is None:
        raise RuntimeError("could not find Gradio's FastAPI server app to mount onto")
    # a2a_app already defines /open, /secure and /healthz internally, so the
    # sub-apps are mounted individually rather than re-prefixing the whole app.
    for route in a2a_app.routes:
        path = getattr(route, "path", "")
        if path in ("/open", "/secure"):
            server_app.mount(path, route.app)


if __name__ == "__main__":
    # prevent_thread_lock returns once the server is up, so we can mount onto it,
    # then we block ourselves instead of letting launch() do it.
    # ssr_mode=False: Gradio 6 otherwise fronts Python with a Node SSR proxy,
    # and the A2A routes mounted on the Python app are not reachable through it.
    demo.launch(prevent_thread_lock=True, ssr_mode=False)
    _attach_a2a(demo)
    demo.block_thread()
