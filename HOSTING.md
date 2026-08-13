# Where to host the A2A test agent — options and recommendation

Researched 2026-08-13. Goal: a **shareable public URL** serving an A2A agent card, with an
auth and a no-auth variant, on a **free** tier, good enough to test the KAYA External Agent node.

## The constraint that eliminates most options

A2A needs three things a plain static host can't give you:

1. **A POST endpoint** that speaks JSON-RPC — so no static/CDN-only hosting.
2. **SSE streaming** held open for the duration of a task — this is what kills naive
   serverless picks.
3. **A stable hostname** you can paste into Discovery Config and share.

Nothing here needs a database, a GPU, or persistence. The agent echoes text.

## Options

| Platform | Free tier reality | SSE | Sleeps? | Verdict |
|---|---|---|---|---|
| **Render** | 750 instance-hrs/mo, Docker or native Python | Yes, long-lived | **Yes — 15 min idle, ~1 min cold start** | ✅ **Recommended** |
| **Koyeb** | Forever-free instance, 512 MB / 0.1 vCPU | Yes | No | ✅ Best if you need always-on |
| **Hugging Face Spaces** | Free Docker Space, public URL | Yes | Yes, idles out | ⚠️ Works; ML-branded URL is odd for a partner demo |
| **Vercel** | Hobby: 300 s max duration, streaming supported | Yes, ≤300 s | No, but per-request | ⚠️ Works, but serverless-per-request fights A2A's task model |
| **Cloudflare Workers** | 100k req/day, **10 ms CPU** per request (waiting is free) | Yes | No | ⚠️ 10 ms CPU is tight; needs a Workers-specific rewrite, not FastAPI |
| **Deno Deploy** | 1M req/mo, 50 ms CPU/request | Yes | No | ⚠️ Would need a TypeScript rewrite — no Python SDK |
| **Fly.io** | **Free tier discontinued.** 2 VM-hours / 7-day trial, then card required | Yes | n/a | ❌ Not free any more |
| **Railway** | Trial credit only, then paid | Yes | No | ❌ Not a standing free tier |
| **ngrok / localtunnel** | Free tunnel to your laptop | Yes | Laptop-dependent | ❌ Not shareable — dies when you close the lid |

Sources at the bottom.

## Recommendation

### Primary: **Render free tier**

Why:
- **`a2a-sdk` is Python.** Render runs the official SDK unchanged — no rewrite. Cloudflare and
  Deno would both mean re-implementing the protocol by hand, which is exactly the wrong thing
  to do when you're trying to test *KAYA*, not your own agent.
- **Long-lived SSE works** — it's a real container, not a per-request function.
- **`render.yaml` is committed here**, so deploy is connect-repo-and-go.
- Sleeping is survivable: hit `/healthz` before a demo, or cron-ping it.

The 15-minute sleep is the one real cost. If someone opens your shared link cold, they wait
~1 minute. For a partner-facing demo, warm it first.

### If sleep is unacceptable: **Koyeb**

Forever-free instance that doesn't idle out. Same Dockerfile works. Slightly less RAM
(512 MB), irrelevant for an echo agent. Take this if you want to share a link that's always
instantly live.

### Not Vercel, despite being the obvious guess

It *would* work — Hobby allows 300 s and supports streaming. But every A2A call becomes a
cold-ish serverless invocation, and the in-memory task store resets between them, so
`tasks/get` on a previous task can miss. You'd be debugging your test harness instead of
KAYA's node. Use Vercel for the v0 prototype frontend, not for this.

## Deploy sequence (Render)

```bash
cd _bmad-output/a2a-test-agent
git init && git add . && git commit -m "A2A test agent"
# push to a GitHub repo, then in Render: New Web Service → pick the repo
```

Then, in order — the second step is the one people miss:

1. First deploy succeeds; note the URL, e.g. `https://kaya-a2a-test.onrender.com`.
2. **Set `PUBLIC_BASE_URL` to that URL and redeploy.** The card's `url` field is built from it.
   Leave it as `localhost` and KAYA fetches the card fine, then fails to invoke — which looks
   like a KAYA bug and isn't.
3. Copy the generated `A2A_TOKEN` from Environment.
4. Verify before sharing:

```bash
BASE=https://kaya-a2a-test.onrender.com TOKEN=<token> bash acceptance.sh
# expect: 13 passed, 0 failed
```

5. Share:
   - no-auth card → `https://kaya-a2a-test.onrender.com/open/.well-known/agent-card.json`
   - bearer card → `https://kaya-a2a-test.onrender.com/secure/.well-known/agent-card.json`

## Security note

`A2A_TOKEN` is a shared static bearer token guarding an echo endpoint that holds no data. That
is appropriate for a throwaway test agent and nothing more. Do not reuse this pattern, or this
token, for anything that touches real workspace data — and rotate it via Render's Environment
tab when you're done sharing, since anyone with the link and token can invoke it.

## Sources

- [Vercel function limits](https://vercel.com/docs/functions/limitations) — Hobby 300 s max, streaming supported
- [Render free tier docs](https://render.com/docs/free) and [2026 free-tier roundup](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026) — 750 hrs/mo, 15 min spin-down
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/about/pricing) — 10 ms CPU free tier
- [Koyeb pricing FAQ](https://www.koyeb.com/docs/faqs/pricing) — forever-free instance
- [Fly.io billing](https://fly.io/docs/about/billing/) — free tier discontinued
- [Deno Deploy pricing](https://deno.com/deploy/pricing) — 50 ms CPU/request
- [Docker Spaces](https://huggingface.co/docs/hub/en/spaces-sdks-docker) — free Docker hosting, idles
- [a2a-sdk on PyPI](https://pypi.org/project/a2a-sdk/) — `0.3.26` is the last 0.3-line release; `1.x` speaks A2A 1.0
