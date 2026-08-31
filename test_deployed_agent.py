"""
Test the agent pipeline locally via ADK Runner (same code as deployed, no SSE timeout).
Run: $env:PYTHONUNBUFFERED=1; .\.venv\Scripts\python.exe test_deployed_agent.py
"""
import sys
sys.stdout.reconfigure(line_buffering=True)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import json
import time
import asyncio
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

GCS_BUCKET = "acn-cda-adk-staging"
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
            args_str = json.dumps(fc.get("args", {}))[:200]
            print(f"{ts()} [{author}] TOOL → {fc.get('name')}({args_str})")
        elif part.get("function_response"):
            fr = part["function_response"]
            resp_str = str(fr.get("response", ""))[:400]
            print(f"{ts()} [{author}] RESP ← {fr.get('name')}: {resp_str}")
    if event.get("actions", {}).get("state_delta"):
        keys = list(event["actions"]["state_delta"].keys())
        print(f"{ts()} [{author}] STATE: {keys}")


_default_query = (
    "For brand Dove, campaign CMP_2025_0107 (objective: Conversion), "
    "show me the daily trend of Total Ad Spend, Impressions, and Clicks as charts. "
    "Also provide a channel-wise comparison and overall campaign performance summary."
)
query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else _default_query

print("=" * 70)
print("QUERY:", query)
print("=" * 70 + "\n")
print(f"{ts()} Starting ADK local runner (same code as deployed, no SSE timeout) ...\n")


async def run():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types
    from root.agent import root_agent

    session_service = InMemorySessionService()

    # Provide GCS artifact service so sub-agents can read/write artifacts
    artifact_service = None
    try:
        from google.adk.artifacts import GcsArtifactService
        artifact_service = GcsArtifactService(bucket_name=GCS_BUCKET)
        print(f"{ts()} GcsArtifactService → gs://{GCS_BUCKET}\n")
    except Exception as ae:
        print(f"{ts()} WARNING: GcsArtifactService unavailable ({ae}) — continuing without\n")

    runner_kwargs = dict(
        agent=root_agent,
        app_name="rmn-report-gen",
        session_service=session_service,
    )
    if artifact_service is not None:
        runner_kwargs["artifact_service"] = artifact_service

    runner = Runner(**runner_kwargs)

    session = await session_service.create_session(
        app_name="rmn-report-gen",
        user_id="test-user",
    )
    session_id = session.id
    print(f"{ts()} Session: {session_id}\n")

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=query)],
    )

    event_count = 0
    async for event in runner.run_async(
        user_id="test-user",
        session_id=session_id,
        new_message=message,
    ):
        event_count += 1
        try:
            event_dict = event.model_dump()
        except Exception:
            event_dict = {
                "author": getattr(event, "author", "?"),
                "content": getattr(event, "content", None),
                "actions": getattr(event, "actions", None),
            }
        print_event(event_dict)

    elapsed = time.time() - START
    print(f"\n{ts()} Pipeline finished — {event_count} events, {elapsed:.0f}s total\n")

    # ── GCS verification ─────────────────────────────────────────────────────
    print("=" * 70)
    print(f"{ts()} Checking GCS for output files (session={session_id}) ...")
    print("=" * 70)
    try:
        from google.cloud import storage as gcs
        client = gcs.Client(project="acn-cda")
        bucket = client.bucket(GCS_BUCKET)
        prefixes = [
            f"root/user/{session_id}/",
            f"users/test-user/sessions/{session_id}/",
            f"agent_state/{session_id}/",
        ]
        found = []
        for prefix in prefixes:
            for b in bucket.list_blobs(prefix=prefix, max_results=100):
                found.append(b)
        if found:
            print(f"\n{ts()} Files written ({len(found)} total):")
            for b in sorted(found, key=lambda x: x.size or 0, reverse=True):
                kb = (b.size or 0) // 1024
                print(f"  [{kb:>5} KB]  gs://{GCS_BUCKET}/{b.name}")
            pdfs = [b for b in found if b.name.lower().endswith(".pdf")]
            if pdfs:
                print(f"\n{ts()} PDF REPORT:")
                for b in pdfs:
                    print(f"  https://storage.cloud.google.com/{GCS_BUCKET}/{b.name}")
        else:
            print(f"\n{ts()} No files found for this session in GCS.")
    except Exception as ex:
        print(f"{ts()} GCS check error: {ex}")


asyncio.run(run())
print(f"\n{ts()} Done. Total elapsed: {time.time()-START:.0f}s")