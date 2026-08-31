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

# ── Stream query ──────────────────────────────────────────────────────────────
print(f"{ts()} Starting stream_query() — pipeline takes ~10-20 min server-side ...")
print(f"{ts()} Stream may close early (inactivity timeout). GCS poll will continue after.\n")

event_count = 0
last_event_tool = None
stream_start = time.time()

try:
    for event in agent.stream_query(
        message=query,
        user_id="test-user",
        session_id=session_id,
    ):
        event_count += 1
        # Track last tool called
        content = event.get("content") or {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        for part in parts:
            if isinstance(part, dict) and part.get("function_call"):
                last_event_tool = part["function_call"].get("name")
        print_event(event)
except Exception as stream_err:
    print(f"\n{ts()} Stream error: {stream_err}")

stream_elapsed = time.time() - stream_start
print(f"\n{ts()} Stream ended — {event_count} events in {stream_elapsed:.0f}s")
print(f"{ts()} Last tool seen: {last_event_tool}")

# ── GCS poll — keep polling for 20 minutes after stream ends ──────────────────
print(f"\n{'=' * 70}")
print(f"{ts()} Stream closed. Now polling GCS for results for up to 20 min ...")
print(f"{ts()} (If backend continues running, files will appear here)")
print(f"{'=' * 70}\n")

try:
    from google.cloud import storage as gcs
    gcs_client = gcs.Client(project=PROJECT)
    bucket = gcs_client.bucket(GCS_BUCKET)

    # Search patterns (most-specific first)
    # PDF writes to: gs://acn-cda-adk-staging/root/user/{session_id}/final_report.pdf
    # Artifacts (charts) write via ADK save_artifact to artifacts/users/USER/sessions/SID/
    search_prefixes = [
        f"root/user/{session_id}/",                          # PDF report location
        f"users/test-user/sessions/{session_id}/",          # ADK artifact session path
        f"artifacts/users/test-user/sessions/{session_id}/",# ADK artifact alternate path
        f"agent_state/{session_id}/",                       # ADK state storage
    ]

    found_files: set[str] = set()
    POLL_INTERVAL   = 30   # seconds between GCS polls
    POLL_MAX        = 1200 # 20 minutes

    poll_start = time.time()
    poll_round = 0

    while time.time() - poll_start < POLL_MAX:
        poll_round += 1
        new_files = []

        for prefix in search_prefixes:
            blobs = list(bucket.list_blobs(prefix=prefix, max_results=50))
            for b in blobs:
                if b.name not in found_files:
                    found_files.add(b.name)
                    new_files.append(b)

        if new_files:
            print(f"{ts()} NEW FILES detected (round {poll_round}):")
            for b in new_files:
                size = b.size or 0
                print(f"  gs://{GCS_BUCKET}/{b.name}  [{size} bytes]  [{b.updated}]")
            print()

            # Check if PDF or report files appeared (pipeline complete)
            done_keys = {"final_report.pdf", "report.pdf", "report_markdown", "report_json"}
            pdf_files = [b for b in new_files if "final_report.pdf" in b.name.lower() or b.name.lower().endswith(".pdf")]
            if any(any(k in b.name.lower() for k in done_keys) for b in new_files):
                print(f"\n{ts()} REPORT FILES DETECTED - pipeline completed!")
                if pdf_files:
                    for b in pdf_files:
                        gcs_uri = f"gs://{GCS_BUCKET}/{b.name}"
                        https_uri = f"https://storage.cloud.google.com/{GCS_BUCKET}/{b.name}"
                        print(f"  PDF GCS  : {gcs_uri}")
                        print(f"  PDF HTTPS: {https_uri}")
                break
        else:
            waited = int(time.time() - poll_start)
            print(f"{ts()} Polling... (round {poll_round}, {waited}s elapsed, session={session_id})")

        time.sleep(POLL_INTERVAL)

    # Final GCS summary
    print(f"\n{ts()} Poll ended. Total files found for session:")
    if found_files:
        for name in sorted(found_files):
            print(f"  gs://{GCS_BUCKET}/{name}")
    else:
        print("  None — backend did NOT write any files (likely stopped when stream closed)")
        print()
        print("  DEBUG: Checking most recent files in bucket (any session)...")
        all_blobs = sorted(
            bucket.list_blobs(max_results=100),
            key=lambda b: b.updated or datetime.min,
            reverse=True,
        )[:15]
        for b in all_blobs:
            print(f"    gs://{GCS_BUCKET}/{b.name}  [{b.updated}]")

except Exception as ex:
    print(f"{ts()} GCS error: {ex}")
    import traceback
    traceback.print_exc()

print(f"\n{ts()} Done. Total elapsed: {time.time()-START:.0f}s")