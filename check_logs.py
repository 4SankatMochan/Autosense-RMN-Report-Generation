"""
Check Cloud Logging for Agent Engine server-side events and errors.
Run: .\.venv\Scripts\python.exe check_logs.py [hours_back]
     .\.venv\Scripts\python.exe check_logs.py 1   # last 1 hour only
"""
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from google.cloud import logging as cloud_logging
from datetime import datetime, timedelta, timezone
import sys

PROJECT = "acn-cda"
RESOURCE_NAME = "projects/350875723330/locations/us-central1/reasoningEngines/6514040695840309248"
HOURS_BACK = int(sys.argv[1]) if len(sys.argv) > 1 else 2

client = cloud_logging.Client(project=PROJECT)

end = datetime.now(timezone.utc)
start = end - timedelta(hours=HOURS_BACK)

filter_str = (
    f'resource.type="aiplatform.googleapis.com/ReasoningEngine" '
    f'timestamp>="{start.strftime("%Y-%m-%dT%H:%M:%SZ")}" '
    f'timestamp<="{end.strftime("%Y-%m-%dT%H:%M:%SZ")}"'
)

print(f"Fetching Agent Engine logs: last {HOURS_BACK}h  ({start.strftime('%H:%M')} → {end.strftime('%H:%M')} UTC)")
print(f"Resource: {RESOURCE_NAME}\n")

entries = list(client.list_entries(filter_=filter_str, page_size=500, order_by="timestamp asc"))
print(f"Found {len(entries)} log entries\n{'='*70}")

for entry in entries:
    ts = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else "??:??:??"
    sev = getattr(entry, "severity", "INFO")
    payload = entry.payload
    if isinstance(payload, dict):
        msg = payload.get("message", payload.get("textPayload", str(payload)))
    else:
        msg = str(payload)
    msg = msg.strip()[:700]
    if msg:
        print(f"[{ts}] [{sev}] {msg}")

if not entries:
    print("No logs found.")
    print("Note: Use resource.type='aiplatform.googleapis.com/ReasoningEngine' (confirmed working)")

print(f"\n{'='*70}")
print("Also checking Cloud Run (OOM errors)...")
cr_filter = (
    f'resource.type="cloud_run_revision" severity>=WARNING '
    f'timestamp>="{start.strftime("%Y-%m-%dT%H:%M:%SZ")}"'
)
cr_entries = list(client.list_entries(filter_=cr_filter, page_size=30, order_by="timestamp asc"))
print(f"Cloud Run WARNING+ entries: {len(cr_entries)}")
for entry in cr_entries:
    ts = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else "?"
    payload = entry.payload
    msg = payload.get("message", str(payload))[:500] if isinstance(payload, dict) else str(payload)[:500]
    print(f"  [{ts}] [CR] {msg.strip()}")