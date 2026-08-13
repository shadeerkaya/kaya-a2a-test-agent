# KAYA A2A Test Agent

A shareable A2A **v0.3** agent for exercising the KAYA External Agent node (REQ-0230 / KAPC-6397).

One deployment serves **two agents** — so a single URL covers both the no-auth and the
bearer-auth test paths:

| | Card URL (GET, authoring) | Endpoint (POST, execution) | Auth |
|---|---|---|---|
| **Open** | `{BASE}/open/.well-known/agent-card.json` | `{BASE}/open/` | none |
| **Secure** | `{BASE}/secure/.well-known/agent-card.json` | `{BASE}/secure/` | `Bearer $A2A_TOKEN` |

Both expose **2 skills** (`echo`, `slow_echo`) so multi-skill routing is testable, and both
declare `streaming: true`.

> The secure **card** is deliberately public — KAYA has to fetch the card *before* it has
> credentials configured. Only the invocation endpoint enforces the token.

## Verified working

`acceptance.sh` — 13 assertions, all passing against a real HTTP server on `a2a-sdk==0.3.26`:
card fetch, `protocolVersion 0.3.0`, 2 skills, streaming flag, open invoke, 401 on missing token,
401 on wrong token, 200 on correct token, SSE event count, progress artifacts, `final: true`.

```bash
BASE=https://your-app.onrender.com TOKEN=<your-token> bash acceptance.sh
```

## Run locally

```bash
pip install -r requirements.txt
A2A_TOKEN=secret123 PUBLIC_BASE_URL=http://localhost:10000 \
  uvicorn app:app --port 10000

curl -s http://localhost:10000/ | jq          # lists both card + endpoint URLs
```

> Port 10000 may already be taken — an A2A Currency Agent was found listening there on this
> machine. Use another port if so.

## Deploy (Render free tier — recommended)

1. Push this directory to a GitHub repo.
2. Render → **New Web Service** → connect the repo. `render.yaml` is picked up automatically.
3. After the first deploy, set `PUBLIC_BASE_URL` to the real URL
   (`https://<service>.onrender.com`) and redeploy.
   **This matters:** `PUBLIC_BASE_URL` becomes the card's `url` field. If it still says
   `localhost`, KAYA will fetch the card fine and then fail to invoke it.
4. Read the generated `A2A_TOKEN` from the Render dashboard → Environment.
5. Share the two card URLs.

Free tier sleeps after 15 min idle, ~1 min cold start. Hit `/healthz` to wake it before a demo,
or keep it warm with a cron ping.

## Test-matrix coverage

| Scenario | How |
|---|---|
| Card fetch succeeds | point Discovery Config at either card URL |
| Skill list is card-driven | 2 skills appear; neither is invented by KAYA |
| Streaming | send text containing `slow` → 3 progress artifacts, then result, then `final: true` |
| No-auth path | use `/open` |
| Bearer path | use `/secure` + token in Vault |
| Auth failure handling | configure `/secure` with a wrong token → 401 |
| Auth expiry | rotate `A2A_TOKEN` in the host, leave KAYA's stale → 401 |
| Card drift | edit `_skills()`, redeploy → snapshot hash changes, drift should surface |
| Skill removed | delete `slow_echo`, redeploy → KAYA should block per KAPC-6405 |
| Fetch timeout | stop the service → fetch fails, previous snapshot must be retained |
| Endpoint ≠ card host | set `PUBLIC_BASE_URL` to a different host than the fetch URL |

## Known limits (deliberate)

- **Not a real agent.** Echoes input. No LLM, no cost.
- **In-memory task store.** Restart loses task history. Fine for node testing; irrelevant to
  the card contract.
- **`slow_echo` is triggered by input text, not a `skillId` field** — because A2A v0.3 has no
  `skillId` on the wire (gap G1 in
  [`docs/features/integrations/a2a-external-agent-node.md`](../../docs/features/integrations/a2a-external-agent-node.md)).
  The executor also reads `message.metadata.skillId`, so KAYA can experiment with that
  convention. Whatever KAYA settles on, this agent can be adjusted in one function.
- **No `pushNotifications`.** Declared `false`. Add later if KAPC-6405's callback path needs it.
- **`cancel` raises `NotImplementedError`** — `tasks/cancel` will error. Add if needed.
