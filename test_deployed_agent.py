"""
Test the deployed Agent Engine - stream + long GCS poll.
Run: $env:PYTHONUNBUFFERED=1; .\.venv\Scripts\python.exe test_deployed_agent.py
"""
import sys
sys.stdout.reconfigure(line_buffering=True)  # flush every print() immediately

# Fix Accenture/Zscaler corporate SSL proxy - must be before all other imports
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    raise SystemExit(
        "ERROR: 'truststore' not installed. Run:  .venv\\Scripts\\pip install truststore"
    )

import json
import time
from datetime import datetime
import vertexai
from vertexai import agent_engines

PROJECT      = "acn-cda"
LOCATION     = "us-central1"
DISPLAY_NAME = "report-gen-v2"
GCS_BUCKET   = "acn-cda-adk-staging"
# Pin to the specific engine deployed with all Playground + visualization fixes.
# Set to None to fall back to display-name lookup (picks newest by resource ID).
RESOURCE_ID  = "4911709206542811136"

vertexai.init(project=PROJECT, location=LOCATION)
START = time.time()


def ts():
    return f"[{datetime.now().strftime('%H:%M:%S')} +{time.time()-START:.0f}s]"


def print_event(event):
    if not isinstance(event, dict):
        return
    author  = event.get("author", "system")
    content = event.get("content") or {}
    parts   = content.get("parts", []) if isinstance(content, dict) else []

    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("text"):
            print(f"{ts()} [{author}] TEXT:\n{part['text']}\n")
        elif part.get("function_call"):
            fc = part["function_call"]
            args_str = json.dumps(fc.get("args", {}))[:300]
            print(f"{ts()} [{author}] TOOL → {fc.get('name')}({args_str})")
        elif part.get("function_response"):
            fr = part["function_response"]
            resp_str = str(fr.get("response", ""))[:600]
            print(f"{ts()} [{author}] RESP ← {fr.get('name')}: {resp_str}")
        elif part.get("file_data"):
            d = part["file_data"]
            print(f"{ts()} [{author}] FILE: {d.get('mime_type')} → {d.get('file_uri')}")
        elif part.get("inline_data"):
            d = part["inline_data"]
            print(f"{ts()} [{author}] BINARY: {d.get('mime_type')} ({len(d.get('data',''))} bytes)")

    # Also check for state updates
    if event.get("actions"):
        actions = event["actions"]
        if actions.get("state_delta"):
            keys = list(actions["state_delta"].keys())
            print(f"{ts()} [{author}] STATE UPDATE: keys={keys}")


# ── Find agent ────────────────────────────────────────────────────────────────
if RESOURCE_ID:
    print(f"{ts()} Using pinned resource ID {RESOURCE_ID} ...")
    resource_name = f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{RESOURCE_ID}"
    agent = agent_engines.get(resource_name)
else:
    print(f"{ts()} Looking up '{DISPLAY_NAME}' ...")
    matches = [e for e in agent_engines.list() if e.display_name == DISPLAY_NAME]
    if not matches:
        print("ERROR: Agent not found.")
        exit(1)
    # Sort by numeric resource ID (highest = most recently created)
    matches.sort(key=lambda e: int(e.resource_name.split("/")[-1]))
    agent = matches[-1]

print(f"{ts()} Found: {agent.resource_name}\n")

# ── Session ───────────────────────────────────────────────────────────────────
sess = agent.create_session(user_id="test-user")
session_id = sess["id"]
print(f"{ts()} Session: {session_id}\n")

import sys as _sys
_default_query = (
    "For brand Dove, campaign CMP_2025_0107 (objective: Conversion), "
    "show me the daily trend of Total Ad Spend, Impressions, and Clicks as charts. "
    "Also provide a channel-wise comparison and overall campaign performance summary."
)
query = " ".join(_sys.argv[1:]) if len(_sys.argv) > 1 else _default_query
print("=" * 70)
print("QUERY:", query)
print("=" * 70 + "\n")

# ── Query via direct REST API (non-streaming, no SSE timeout) ─────────────────
# AgentEngine SDK only exposes stream_query() which has a ~15s SSE inactivity
# timeout — kills long pipelines. The underlying REST API has a :query endpoint
# (synchronous HTTP POST, no SSE timer). We call it directly with a 15-min timeout.
import urllib.request as _urllib
import google.auth as _gauth
import google.auth.transport.requests as _gatr

print(f"{ts()} Calling :query REST endpoint — blocking until pipeline completes ...")

_RESOURCE = agent.resource_name  # e.g. projects/.../reasoningEngines/NNN
_URL = f"https://us-central1-aiplatform.googleapis.com/v1beta1/{_RESOURCE}:query"
_TIMEOUT = 900  # 15 min — abort if pipeline takes longer

query_start = time.time()
query_response = None
try:
    _creds, _ = _gauth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    _creds.refresh(_gatr.Request())

    _payload = json.dumps({
        "input": {
            "message": query,
            "session_id": session_id,
            "user_id": "test-user",
        }
    }).encode()

    _req = _urllib.Request(
        _URL,
        data=_payload,
        headers={
            "Authorization": f"Bearer {_creds.token}",
            "Content-Type": "application/json",
        },
    )
    with _urllib.urlopen(_req, timeout=_TIMEOUT) as _resp:
        query_response = json.loads(_resp.read())

    elapsed = time.time() - query_start
    print(f"\n{ts()} Pipeline completed in {elapsed:.0f}s")
    # Print the agent's final text response
    output = query_response.get("output", query_response)
    if isinstance(output, dict):
        content = output.get("content") or {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                print(f"\n{'='*70}\nAGENT RESPONSE:\n{part['text']}\n{'='*70}")
    if not any(
        isinstance(output, dict) and
        isinstance(output.get("content"), dict) and
        any(p.get("text") for p in output.get("content", {}).get("parts", []))
        for _ in [None]
    ):
        print(f"\nRaw response (first 3000 chars):\n{str(query_response)[:3000]}")

except Exception as qerr:
    elapsed = time.time() - query_start
    print(f"\n{ts()} REST query error after {elapsed:.0f}s: {qerr}")
    import traceback; traceback.print_exc()

# ── GCS verification — run once after query() completes ──────────────────────
print(f"\n{'=' * 70}")
print(f"{ts()} Verifying GCS output files for session {session_id} ...")
print(f"{'=' * 70}\n")

try:
    from google.cloud import storage as gcs
    gcs_client = gcs.Client(project=PROJECT)
    bucket = gcs_client.bucket(GCS_BUCKET)

    search_prefixes = [
        f"root/user/{session_id}/",
        f"users/test-user/sessions/{session_id}/",
        f"artifacts/users/test-user/sessions/{session_id}/",
        f"agent_state/{session_id}/",
    ]

    found_files = []
    for prefix in search_prefixes:
        for b in bucket.list_blobs(prefix=prefix, max_results=100):
            found_files.append(b)

    if found_files:
        print(f"{ts()} Files written for this session ({len(found_files)} total):")
        for b in sorted(found_files, key=lambda x: x.updated or datetime.min, reverse=True):
            size_kb = (b.size or 0) // 1024
            print(f"  [{size_kb:>5} KB]  gs://{GCS_BUCKET}/{b.name}")
        pdf_files = [b for b in found_files if b.name.lower().endswith(".pdf")]
        if pdf_files:
            print(f"\n{ts()} PDF REPORT:")
            for b in pdf_files:
                print(f"  https://storage.cloud.google.com/{GCS_BUCKET}/{b.name}")
    else:
        print(f"{ts()} No files found — pipeline may not have completed.")

except Exception as ex:
    print(f"{ts()} GCS check error: {ex}")

print(f"\n{ts()} Done. Total elapsed: {time.time()-START:.0f}s")