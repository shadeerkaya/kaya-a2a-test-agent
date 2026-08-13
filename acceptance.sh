#!/bin/bash
# Acceptance run against the deployed test agent.
# Usage: BASE=http://localhost:10099 TOKEN=secret123 bash acceptance.sh
BASE="${BASE:-http://localhost:10099}"
TOKEN="${TOKEN:-secret123}"
pass=0; fail=0
chk() { if [ "$2" = "$3" ]; then echo "  PASS  $1 ($2)"; pass=$((pass+1)); else echo "  FAIL  $1 — got '$2' want '$3'"; fail=$((fail+1)); fi; }

send() { # $1=mount $2=authheader $3=text
  curl -s -m 20 -X POST "$BASE/$1/" -H 'Content-Type: application/json' \
    ${2:+-H "Authorization: $2"} \
    -d "{\"jsonrpc\":\"2.0\",\"id\":\"t\",\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"kind\":\"message\",\"messageId\":\"m-$RANDOM\",\"parts\":[{\"kind\":\"text\",\"text\":\"$3\"}]}}}"
}

echo "== 1. open card fetch"
c=$(curl -s -m 10 "$BASE/open/.well-known/agent-card.json")
chk "protocolVersion" "$(echo "$c" | python3 -c 'import json,sys;print(json.load(sys.stdin)["protocolVersion"])')" "0.3.0"
chk "skill count"     "$(echo "$c" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["skills"]))')" "2"
chk "streaming"       "$(echo "$c" | python3 -c 'import json,sys;print(json.load(sys.stdin)["capabilities"]["streaming"])')" "True"
chk "open has no auth" "$(echo "$c" | python3 -c 'import json,sys;print("securitySchemes" in json.load(sys.stdin) and json.load(sys.stdin) is not None)' 2>/dev/null || echo False)" "False"

echo "== 2. secure card fetch (must be public, no creds)"
s=$(curl -s -m 10 "$BASE/secure/.well-known/agent-card.json")
chk "declares bearer" "$(echo "$s" | python3 -c 'import json,sys;print(json.load(sys.stdin)["securitySchemes"]["bearer"]["scheme"])')" "bearer"

echo "== 3. open endpoint invoke, no creds"
r=$(send open "" "hello kaya")
chk "artifact text" "$(echo "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["artifacts"][0]["parts"][0]["text"])')" "echo: hello kaya"
chk "task state"    "$(echo "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["status"]["state"])')" "completed"

echo "== 4. secure endpoint rejects missing token"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -X POST "$BASE/secure/" -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","kind":"message","messageId":"x","parts":[{"kind":"text","text":"hi"}]}}}')
chk "401 no token" "$code" "401"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -X POST "$BASE/secure/" -H 'Content-Type: application/json' -H 'Authorization: Bearer wrong' -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","kind":"message","messageId":"x","parts":[{"kind":"text","text":"hi"}]}}}')
chk "401 bad token" "$code" "401"

echo "== 5. secure endpoint accepts good token"
r=$(send secure "Bearer $TOKEN" "authed hello")
chk "authed artifact" "$(echo "$r" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["artifacts"][0]["parts"][0]["text"])')" "echo: authed hello"

echo "== 6. streaming, ends with final:true"
ev=$(curl -sN -m 25 -X POST "$BASE/open/" -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
  -d '{"jsonrpc":"2.0","id":"s","method":"message/stream","params":{"message":{"role":"user","kind":"message","messageId":"ms","parts":[{"kind":"text","text":"slow stream test"}]}}}' \
  | python3 -c "
import sys,json
n=0; final=False; arts=0
for line in sys.stdin:
    line=line.strip()
    if not line.startswith('data:'): continue
    n+=1; r=json.loads(line[5:]).get('result',{})
    if r.get('kind')=='artifact-update': arts+=1
    if r.get('final') is True: final=True
print(f'{n} {arts} {final}')
")
set -- $ev
chk "got >=5 SSE events" "$([ "$1" -ge 5 ] && echo yes || echo no)" "yes"
chk "progress artifacts" "$([ "$2" -ge 3 ] && echo yes || echo no)" "yes"
chk "final:true present" "$3" "True"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1
