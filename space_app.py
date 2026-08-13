"""Hugging Face Spaces (Gradio SDK) entrypoint.

The Docker SDK is a paid feature, but the Gradio SDK is free and Gradio runs on
FastAPI/uvicorn. So we build our A2A FastAPI app and mount a tiny Gradio status
page onto it, then serve the whole thing on 7860. The A2A routes are unchanged.
"""
import os

import gradio as gr
from gradio.routes import mount_gradio_app

from app import BASE, app as a2a_app

with gr.Blocks(title="KAYA A2A Test Agent") as page:
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

demo = mount_gradio_app(a2a_app, page, path="/ui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(demo, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
