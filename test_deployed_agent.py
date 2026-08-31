"""
Test the deployed Agent Engine.
Run: python test_deployed_agent.py
"""
# Fix Accenture/Zscaler corporate SSL proxy — must be before all other imports
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
DISPLAY_NAME = "report-gen-v1"
GCS_BUCKET   = "acn-cda-adk-staging"

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
            print(f"{ts()} [{author}] TOOL → {fc.get('name')}({json.dumps(fc.get('args',{}))[:200]})")
        elif part.get("function_response"):
            fr = part["function_response"]
            print(f"{ts()} [{author}] RESP ← {fr.get('name')}: {str(fr.get('response',''))[:400]}")
        elif part.get("file_data"):
            d = part["file_data"]
            print(f"{ts()} [{author}] FILE: {d.get('mime_type')} → {d.get('file_uri')}")
        elif part.get("inline_data"):
            d = part["inline_data"]
            print(f"{ts()} [{author}] BINARY: {d.get('mime_type')} ({len(d.get('data',''))} bytes)")


# ── Find agent ────────────────────────────────────────────────────────────────
print(f"{ts()} Looking up '{DISPLAY_NAME}' ...")
matches = [e for e in agent_engines.list() if e.display_name == DISPLAY_NAME]
if not matches:
    print("ERROR: Agent not found.")
    exit(1)

agent = matches[-1]
print(f"{ts()} Found: {agent.resource_name}\n")

# ── Session ───────────────────────────────────────────────────────────────────
sess = agent.create_session(user_id="test-user")
session_id = sess["id"]
print(f"{ts()} Session: {session_id}\n")

query = (
    "For brand Dove, campaign CMP_2025_0107 (objective: Conversion), "
    "show me the daily trend of Total Ad Spend, Impressions, and Clicks as charts. "
    "Also provide a channel-wise comparison and overall campaign performance summary."
)
print("=" * 70)
print("QUERY:", query)
print("=" * 70 + "\n")

# ── Try non-streaming query() first ──────────────────────────────────────────
print(f"{ts()} Calling agent.query() — this waits for the FULL response (may take 10-20 min) ...")
print(f"{ts()} Do NOT close this window.\n")

try:
    response = agent.query(
        message=query,
        user_id="test-user",
        session_id=session_id,
    )
    print(f"\n{ts()} ✅ agent.query() completed!\n")
    print("=" * 70)
    if isinstance(response, dict):
        # Try to extract text from the response
        content = response.get("content") or response.get("output") or response
        parts = content.get("parts", []) if isinstance(content, dict) else []
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                print(part["text"])
        if not parts:
            print(json.dumps(response, indent=2, default=str)[:3000])
    else:
        print(str(response)[:3000])
    print("=" * 70)

except Exception as e:
    print(f"{ts()} agent.query() failed or timed out: {e}\n")
    print(f"{ts()} Falling back to stream_query() ...\n")

    event_count = 0
    for event in agent.stream_query(
        message=query,
        user_id="test-user",
        session_id=session_id,
    ):
        event_count += 1
        print_event(event)
    print(f"\n{ts()} Stream ended — {event_count} events")

# ── Search GCS for PDF report ─────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print(f"{ts()} Searching GCS for PDF/report files ...")

try:
    from google.cloud import storage as gcs
    client = gcs.Client(project=PROJECT)
    bucket = client.bucket(GCS_BUCKET)

    # Search with session_id prefix
    prefix_patterns = [
        f"users/test-user/sessions/{session_id}/",
        f"artifacts/users/test-user/sessions/{session_id}/",
        f"artifacts/",
    ]

    found = []
    for prefix in prefix_patterns:
        blobs = list(bucket.list_blobs(prefix=prefix, max_results=20))
        for b in blobs:
            if b.name not in found:
                found.append(b.name)

    if found:
        print(f"{ts()} Files found in GCS:")
        for name in found:
            print(f"  gs://{GCS_BUCKET}/{name}")
    else:
        # Broad search for any recent PDF
        all_blobs = sorted(
            bucket.list_blobs(max_results=200),
            key=lambda b: b.updated,
            reverse=True,
        )
        recent = [b for b in all_blobs[:20]]
        if recent:
            print(f"{ts()} Most recent files in bucket (no session-specific files found):")
            for b in recent:
                print(f"  gs://{GCS_BUCKET}/{b.name}  [{b.updated}]")
        else:
            print(f"{ts()} No files found in gs://{GCS_BUCKET}")

except Exception as ex:
    print(f"{ts()} GCS check error: {ex}")

print(f"\n{ts()} Done.")