"""
Broad Cloud Logging search to find Agent Engine logs.
Run: .\.venv\Scripts\python.exe check_logs2.py
"""
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from google.cloud import logging as cloud_logging
from datetime import datetime, timedelta, timezone

PROJECT = "acn-cda"
client = cloud_logging.Client(project=PROJECT)

end = datetime.now(timezone.utc)
start = end - timedelta(hours=4)

# Try multiple filters
filters = [
    # Broad: any ReasoningEngine / agent engine logs
    'resource.type="aiplatform.googleapis.com/ReasoningEngine"',
    # Try Cloud Run logs (Agent Engine runs on Cloud Run internally)
    'resource.type="cloud_run_revision" severity>=WARNING',
    # Any AI Platform logs
    'resource.type="aiplatform.googleapis.com/Endpoint" severity>=WARNING',
    # Look for stderr/stdout from our agent process
    '"report-gen-v1"',
    '"call_db_ds_agent"',
    '"prompt_generator"',
]

for f in filters:
    full = f'{f} timestamp>="{start.strftime("%Y-%m-%dT%H:%M:%SZ")}"'
    try:
        entries = list(client.list_entries(filter_=full, page_size=20, order_by="timestamp desc"))
        if entries:
            print(f"\n=== FOUND {len(entries)} entries for filter: {f} ===")
            for entry in entries[:5]:
                ts = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else "?"
                sev = getattr(entry, "severity", "INFO")
                payload = entry.payload
                msg = payload.get("message", str(payload))[:400] if isinstance(payload, dict) else str(payload)[:400]
                res_type = entry.resource.type if entry.resource else "?"
                print(f"  [{ts}] [{sev}] [res:{res_type}] {msg}")
        else:
            print(f"No entries: {f}")
    except Exception as e:
        print(f"ERROR for filter '{f}': {e}")

print("\nDone.")