"""
Shareable A2A v0.3 test agent for the KAYA External Agent node (REQ-0230).

Serves TWO independent agents on one deployment, so one URL covers both the
no-auth and the bearer-auth test paths:

  /open/.well-known/agent-card.json    no auth
  /secure/.well-known/agent-card.json  bearer required (A2A_TOKEN)

Each has 2 skills (echo, slow_echo) so multi-skill routing is testable, and
streaming is enabled so SSE + stream-break behaviour is testable.

Local:  A2A_TOKEN=secret123 uvicorn app:app --port 10000
"""
import asyncio
import os

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    HTTPAuthSecurityScheme,
    Part,
    SecurityScheme,
    TextPart,
)
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

TOKEN = os.getenv("A2A_TOKEN", "secret123")

# The card's `url` field must be the real public URL, or KAYA fetches the card
# fine and then fails to invoke it. Render injects RENDER_EXTERNAL_URL, Koyeb
# injects KOYEB_PUBLIC_DOMAIN - prefer those so no manual step is needed.
_koyeb = os.getenv("KOYEB_PUBLIC_DOMAIN")
BASE = (
    os.getenv("PUBLIC_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or (f"https://{_koyeb}" if _koyeb else None)
    or "http://localhost:10000"
).rstrip("/")


class TestAgent(AgentExecutor):
    """echo returns immediately; slow_echo emits progress for streaming tests."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = context.get_user_input() or "(empty input)"
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        await updater.submit()
        await updater.start_work()

        # No skillId field exists in A2A v0.3 (see gap G1) — the caller signals
        # intent through message text or metadata. This POC reads both so KAYA
        # can experiment with either approach.
        meta = context.message.metadata or {} if context.message else {}
        wants_slow = "slow" in text.lower() or meta.get("skillId") == "slow_echo"

        if wants_slow:
            # Progress emitted as artifacts rather than status messages: stable
            # across SDK patch versions and still arrives as discrete SSE events.
            for i in range(1, 4):
                await asyncio.sleep(1)
                await updater.add_artifact(
                    [Part(root=TextPart(text=f"progress {i}/3"))],
                    name=f"progress-{i}",
                )

        await updater.add_artifact(
            [Part(root=TextPart(text=f"echo: {text}"))], name="result"
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported by the test agent")


def _skills() -> list[AgentSkill]:
    return [
        AgentSkill(
            id="echo",
            name="Echo",
            description="Returns the input text prefixed with 'echo:'. Completes immediately.",
            tags=["test", "utility"],
            examples=["hello world"],
            inputModes=["text/plain"],
            outputModes=["text/plain"],
        ),
        AgentSkill(
            id="slow_echo",
            name="Slow Echo",
            description=(
                "Emits 3 progress artifacts one second apart, then echoes. "
                "Send text containing 'slow' to trigger it. Use for streaming tests."
            ),
            tags=["test", "streaming"],
            examples=["slow please"],
            inputModes=["text/plain"],
            outputModes=["text/plain"],
        ),
    ]


def build_card(*, secure: bool) -> AgentCard:
    mount = "/secure" if secure else "/open"
    # Set security in the constructor — the model is populated by alias, so
    # assigning card.securitySchemes afterwards raises "no field".
    extra = {}
    if secure:
        extra = {
            "securitySchemes": {
                "bearer": SecurityScheme(
                    root=HTTPAuthSecurityScheme(
                        type="http", scheme="bearer", bearerFormat="opaque"
                    )
                )
            },
            "security": [{"bearer": []}],
        }
    return AgentCard(
        protocolVersion="0.3.0",
        name="KAYA A2A Test Agent" + (" (bearer auth)" if secure else " (no auth)"),
        description=(
            "Reference A2A v0.3 agent for exercising the KAYA External Agent node. "
            + ("Requires a bearer token." if secure else "Open, no credentials needed.")
        ),
        url=f"{BASE}{mount}/",
        version="1.0.0",
        preferredTransport="JSONRPC",
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=_skills(),
        **extra,
    )


class RequireBearer(BaseHTTPMiddleware):
    """The card only *declares* auth; the SDK does not enforce it. This does."""

    async def dispatch(self, request, call_next):
        # The card itself stays public — KAYA must fetch it before it has creds.
        if request.url.path.endswith("agent-card.json"):
            return await call_next(request)
        header = request.headers.get("authorization", "")
        if header != f"Bearer {TOKEN}":
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32001, "message": "Missing or invalid bearer token"},
                },
            )
        return await call_next(request)


def _sub_app(secure: bool):
    handler = DefaultRequestHandler(
        agent_executor=TestAgent(), task_store=InMemoryTaskStore()
    )
    sub = A2AFastAPIApplication(
        agent_card=build_card(secure=secure), http_handler=handler
    ).build()
    if secure:
        sub.add_middleware(RequireBearer)
    return sub


app = FastAPI(title="KAYA A2A Test Agent")
app.mount("/open", _sub_app(secure=False))
app.mount("/secure", _sub_app(secure=True))


@app.get("/")
def index():
    return {
        "service": "KAYA A2A Test Agent (A2A v0.3)",
        "open": {
            "card": f"{BASE}/open/.well-known/agent-card.json",
            "endpoint": f"{BASE}/open/",
            "auth": "none",
        },
        "secure": {
            "card": f"{BASE}/secure/.well-known/agent-card.json",
            "endpoint": f"{BASE}/secure/",
            "auth": "Bearer <A2A_TOKEN>",
        },
        "skills": ["echo", "slow_echo"],
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}
