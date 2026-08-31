"""
Cloud Run entrypoint for RMN Report Generator API.

Endpoints:
  POST /generate            – start a report generation job, returns {job_id}
  GET  /status/{job_id}     – poll status + accumulated logs + result
  GET  /stream/{job_id}     – SSE stream of live log lines
  GET  /                    – HTML test UI
  GET  /health              – health check
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Optional

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rmn_report_gen")

app = FastAPI(title="RMN Report Generator", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GCS_BUCKET = os.getenv("BUCKET_NAME", "acn-cda-adk-staging")

# ── In-memory job store ───────────────────────────────────────────────────────
# { job_id: { "status": str, "logs": [str], "result": dict|None, "start": float } }
_JOBS: dict = {}
_LOG_QUEUES: dict = {}   # job_id -> asyncio.Queue for SSE streaming


# ── Helper: log & push to queue ───────────────────────────────────────────────
def _log(job_id: str, line: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    msg = f"[{ts}] {line}"
    if job_id in _JOBS:
        _JOBS[job_id]["logs"].append(msg)
    if job_id in _LOG_QUEUES:
        try:
            _LOG_QUEUES[job_id].put_nowait(msg)
        except asyncio.QueueFull:
            pass
    logger.info("[%s] %s", job_id[:8], line)


# ── Pipeline runner ───────────────────────────────────────────────────────────
async def _run_pipeline(job_id: str, query: str) -> None:
    job = _JOBS[job_id]
    _log(job_id, "Pipeline starting …")
    t0 = time.perf_counter()

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types
        from root.agent import root_agent

        session_service = InMemorySessionService()

        artifact_service = None
        try:
            from google.adk.artifacts import GcsArtifactService
            artifact_service = GcsArtifactService(bucket_name=GCS_BUCKET)
            _log(job_id, f"GcsArtifactService → gs://{GCS_BUCKET}")
        except Exception as ae:
            _log(job_id, f"WARNING: GcsArtifactService unavailable ({ae}) — continuing without")

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
            user_id="api-user",
        )
        session_id = session.id
        _log(job_id, f"Session: {session_id}")

        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=query)],
        )

        event_count = 0
        async for event in runner.run_async(
            user_id="api-user",
            session_id=session_id,
            new_message=message,
        ):
            event_count += 1
            try:
                author = getattr(event, "author", "?")
                content = getattr(event, "content", None)
                parts = getattr(content, "parts", []) if content else []
                for part in (parts or []):
                    fc = getattr(part, "function_call", None)
                    fr = getattr(part, "function_response", None)
                    txt = getattr(part, "text", None)
                    if fc:
                        _log(job_id, f"[{author}] → {fc.name}(…)")
                    elif fr:
                        rval = str(getattr(fr, "response", ""))[:120]
                        _log(job_id, f"[{author}] ← {fr.name}: {rval}")
                    elif txt and txt.strip():
                        preview = txt.strip()[:200].replace("\n", " ")
                        _log(job_id, f"[{author}] {preview}")
                actions = getattr(event, "actions", None)
                if actions and getattr(actions, "state_delta", None):
                    keys = list(actions.state_delta.keys())
                    _log(job_id, f"[{author}] STATE: {keys}")
            except Exception:
                pass

        elapsed = time.perf_counter() - t0
        _log(job_id, f"Pipeline done — {event_count} events, {elapsed:.0f}s")

        # ── GCS verification ────────────────────────────────────────────────
        pdf_url = None
        pdf_gcs = None
        chart_urls = []
        try:
            from google.cloud import storage as gcs
            client = gcs.Client()
            bucket = client.bucket(GCS_BUCKET)
            prefix = f"root/user/{session_id}/"
            blobs = list(bucket.list_blobs(prefix=prefix, max_results=200))
            for b in blobs:
                if b.name.lower().endswith(".pdf"):
                    pdf_gcs = f"gs://{GCS_BUCKET}/{b.name}"
                    pdf_url = f"https://storage.cloud.google.com/{GCS_BUCKET}/{b.name}"
                    _log(job_id, f"PDF → {pdf_url}")
                elif b.name.lower().endswith(".png"):
                    chart_urls.append(f"gs://{GCS_BUCKET}/{b.name}")
            _log(job_id, f"GCS: {len(blobs)} files, {len(chart_urls)} charts")
        except Exception as ge:
            _log(job_id, f"GCS check error: {ge}")

        mins, secs = divmod(int(elapsed), 60)
        job["status"] = "done"
        job["result"] = {
            "pdf_gcs": pdf_gcs,
            "pdf_url": pdf_url,
            "chart_urls": chart_urls,
            "session_id": session_id,
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_human": f"{mins}m {secs}s",
            "event_count": event_count,
        }

    except Exception as exc:
        import traceback
        _log(job_id, f"ERROR: {exc}")
        _log(job_id, traceback.format_exc())
        job["status"] = "error"
        job["result"] = {"error": str(exc)}

    finally:
        # Signal SSE stream to close
        if job_id in _LOG_QUEUES:
            try:
                _LOG_QUEUES[job_id].put_nowait("__DONE__")
            except asyncio.QueueFull:
                pass


# ── API models ────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    query: str


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(req: GenerateRequest):
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "status": "running",
        "logs": [],
        "result": None,
        "start": time.time(),
        "query": req.query,
    }
    _LOG_QUEUES[job_id] = asyncio.Queue(maxsize=2000)
    asyncio.create_task(_run_pipeline(job_id, req.query))
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "job not found"}, status_code=404)
    elapsed = round(time.time() - job["start"], 1)
    return {
        "job_id": job_id,
        "status": job["status"],
        "elapsed_seconds": elapsed,
        "logs": job["logs"],
        "result": job["result"],
    }


@app.get("/stream/{job_id}")
async def stream(job_id: str):
    """Server-Sent Events — streams log lines as they arrive."""
    job = _JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "job not found"}, status_code=404)

    queue = _LOG_QUEUES.get(job_id)

    async def event_generator():
        # Replay already-accumulated logs first
        for line in list(job.get("logs", [])):
            yield f"data: {json.dumps({'log': line})}\n\n"

        if queue is None or job["status"] != "running":
            result = job.get("result") or {}
            yield f"data: {json.dumps({'done': True, 'result': result})}\n\n"
            return

        while True:
            try:
                line = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                yield "data: {\"ping\": true}\n\n"
                continue
            if line == "__DONE__":
                result = job.get("result") or {}
                yield f"data: {json.dumps({'done': True, 'result': result})}\n\n"
                break
            yield f"data: {json.dumps({'log': line})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── HTML UI ───────────────────────────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RMN Report Generator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
  .header { background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            padding: 24px 32px; border-bottom: 1px solid #1e40af; }
  .header h1 { font-size: 1.6rem; color: #60a5fa; font-weight: 700; }
  .header p  { color: #94a3b8; margin-top: 4px; font-size: 0.9rem; }
  .container { max-width: 1100px; margin: 32px auto; padding: 0 24px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px;
           padding: 24px; margin-bottom: 24px; }
  .card h2 { font-size: 1rem; color: #94a3b8; margin-bottom: 14px;
              text-transform: uppercase; letter-spacing: .05em; }
  textarea { width: 100%; height: 120px; background: #0f172a; border: 1px solid #334155;
             border-radius: 8px; color: #e2e8f0; padding: 12px; font-size: 0.92rem;
             resize: vertical; outline: none; }
  textarea:focus { border-color: #3b82f6; }
  .row { display: flex; gap: 12px; margin-top: 14px; align-items: center; }
  button { padding: 10px 28px; border: none; border-radius: 8px; font-size: 0.95rem;
           cursor: pointer; font-weight: 600; transition: all .15s; }
  #submitBtn { background: #2563eb; color: #fff; }
  #submitBtn:hover { background: #1d4ed8; }
  #submitBtn:disabled { background: #334155; color: #64748b; cursor: not-allowed; }
  #clearBtn { background: #334155; color: #94a3b8; }
  #clearBtn:hover { background: #475569; }
  .status-badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
  .badge-running { background: #1d4ed8; color: #bfdbfe; }
  .badge-done    { background: #166534; color: #bbf7d0; }
  .badge-error   { background: #991b1b; color: #fecaca; }
  .badge-idle    { background: #374151; color: #9ca3af; }
  #logBox { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px;
            height: 380px; overflow-y: auto; padding: 12px; font-family: monospace;
            font-size: 0.78rem; line-height: 1.55; }
  #logBox .log-line { color: #94a3b8; }
  #logBox .log-tool { color: #60a5fa; }
  #logBox .log-state { color: #a78bfa; }
  #logBox .log-err  { color: #f87171; }
  #logBox .log-done { color: #34d399; font-weight: 600; }
  .result-box { margin-top: 20px; display: none; }
  .result-box.visible { display: block; }
  .result-title { font-size: 1.1rem; color: #34d399; font-weight: 700; margin-bottom: 14px; }
  .metric-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
  .metric { background: #0f172a; border: 1px solid #1e40af; border-radius: 8px;
             padding: 12px 20px; flex: 1; min-width: 160px; }
  .metric .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing:.05em; }
  .metric .value { font-size: 1.3rem; font-weight: 700; color: #60a5fa; margin-top: 4px; }
  .pdf-link { display: inline-block; background: #1d4ed8; color: #fff; padding: 12px 24px;
              border-radius: 8px; text-decoration: none; font-weight: 600; margin-right: 12px;
              margin-bottom: 10px; }
  .pdf-link:hover { background: #2563eb; }
  .gcs-path { font-family: monospace; font-size: 0.82rem; color: #94a3b8;
               background: #0f172a; padding: 10px 14px; border-radius: 6px;
               border: 1px solid #334155; word-break: break-all; margin-top: 10px; }
  .charts-grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
  .chart-item { background: #0f172a; border: 1px solid #334155; border-radius: 8px;
                padding: 8px; font-size: 0.75rem; color: #64748b; word-break: break-all; }
  .elapsed { color: #fbbf24; }
</style>
</head>
<body>
<div class="header">
  <h1>RMN Report Generator</h1>
  <p>AI-powered campaign performance reports &nbsp;·&nbsp; Powered by Vertex AI + ADK</p>
</div>
<div class="container">

  <!-- Query input -->
  <div class="card">
    <h2>Query</h2>
    <textarea id="queryInput" placeholder="Enter your report query…">For brand Dove, campaign CMP_2025_0107 (objective: Conversion), show me the daily trend of Total Ad Spend, Impressions, and Clicks as charts. Also provide a channel-wise comparison and overall campaign performance summary.</textarea>
    <div class="row">
      <button id="submitBtn" onclick="submitQuery()">Generate Report</button>
      <button id="clearBtn" onclick="clearLogs()">Clear</button>
      <span id="statusBadge" class="status-badge badge-idle">IDLE</span>
      <span id="elapsedLabel" style="color:#64748b;font-size:0.85rem;margin-left:8px;"></span>
    </div>
  </div>

  <!-- Logs -->
  <div class="card">
    <h2>Live Logs</h2>
    <div id="logBox"></div>
  </div>

  <!-- Result -->
  <div class="card result-box" id="resultBox">
    <div class="result-title">Report Generated Successfully</div>
    <div class="metric-row">
      <div class="metric"><div class="label">Time Taken</div><div class="value elapsed" id="rTime">—</div></div>
      <div class="metric"><div class="label">Events Processed</div><div class="value" id="rEvents">—</div></div>
      <div class="metric"><div class="label">Charts Generated</div><div class="value" id="rCharts">—</div></div>
    </div>
    <a id="pdfLink" href="#" target="_blank" class="pdf-link" style="display:none">Download PDF Report</a>
    <div id="gcsPath" class="gcs-path" style="display:none"></div>
    <div id="chartsSection"></div>
  </div>

</div>

<script>
let _jobId = null;
let _evtSource = null;
let _startTime = null;
let _elapsedTimer = null;

function setBadge(state) {
  const b = document.getElementById('statusBadge');
  b.className = 'status-badge badge-' + state;
  b.textContent = state.toUpperCase();
}

function appendLog(line, cls) {
  const box = document.getElementById('logBox');
  const d = document.createElement('div');
  d.className = 'log-line ' + (cls || '');
  if (line.includes('→') || line.includes('←')) d.className += ' log-tool';
  if (line.includes('STATE:')) d.className += ' log-state';
  if (line.includes('ERROR') || line.includes('error')) d.className += ' log-err';
  d.textContent = line;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

function clearLogs() {
  document.getElementById('logBox').innerHTML = '';
  document.getElementById('resultBox').classList.remove('visible');
  setBadge('idle');
  clearInterval(_elapsedTimer);
  document.getElementById('elapsedLabel').textContent = '';
}

function startElapsed() {
  _startTime = Date.now();
  _elapsedTimer = setInterval(() => {
    const s = Math.floor((Date.now() - _startTime) / 1000);
    const m = Math.floor(s / 60), sec = s % 60;
    document.getElementById('elapsedLabel').textContent =
      `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')} elapsed`;
  }, 1000);
}

function showResult(result) {
  clearInterval(_elapsedTimer);
  const box = document.getElementById('resultBox');
  document.getElementById('rTime').textContent = result.elapsed_human || result.elapsed_seconds + 's';
  document.getElementById('rEvents').textContent = result.event_count ?? '—';
  document.getElementById('rCharts').textContent = (result.chart_urls || []).length;

  if (result.pdf_url) {
    const link = document.getElementById('pdfLink');
    link.href = result.pdf_url;
    link.style.display = 'inline-block';
  }
  if (result.pdf_gcs) {
    const gcsEl = document.getElementById('gcsPath');
    gcsEl.textContent = result.pdf_gcs;
    gcsEl.style.display = 'block';
  }
  if (result.chart_urls && result.chart_urls.length > 0) {
    const sec = document.getElementById('chartsSection');
    sec.innerHTML = '<div style="color:#94a3b8;font-size:0.8rem;margin-top:14px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em;">Charts in GCS</div><div class="charts-grid">';
    result.chart_urls.forEach(u => {
      sec.innerHTML += `<div class="chart-item">${u}</div>`;
    });
    sec.innerHTML += '</div>';
  }
  box.classList.add('visible');

  const logBox = document.getElementById('logBox');
  const done = document.createElement('div');
  done.className = 'log-line log-done';
  done.textContent = `✓ Done in ${result.elapsed_human || result.elapsed_seconds + 's'}`;
  logBox.appendChild(done);
  logBox.scrollTop = logBox.scrollHeight;
}

async function submitQuery() {
  const query = document.getElementById('queryInput').value.trim();
  if (!query) return;

  clearLogs();
  document.getElementById('submitBtn').disabled = true;
  setBadge('running');
  startElapsed();
  appendLog('Submitting query…');

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query}),
    });
    const data = await res.json();
    _jobId = data.job_id;
    appendLog(`Job ID: ${_jobId}`);
    startStreaming(_jobId);
  } catch (err) {
    appendLog('Failed to start job: ' + err, 'log-err');
    setBadge('error');
    document.getElementById('submitBtn').disabled = false;
  }
}

function startStreaming(jobId) {
  if (_evtSource) _evtSource.close();
  _evtSource = new EventSource(`/stream/${jobId}`);

  _evtSource.onmessage = (e) => {
    const payload = JSON.parse(e.data);
    if (payload.ping) return;
    if (payload.log) appendLog(payload.log);
    if (payload.done) {
      _evtSource.close();
      clearInterval(_elapsedTimer);
      if (payload.result && !payload.result.error) {
        setBadge('done');
        showResult(payload.result);
      } else {
        setBadge('error');
        appendLog('Pipeline finished with error: ' + JSON.stringify(payload.result), 'log-err');
      }
      document.getElementById('submitBtn').disabled = false;
    }
  };

  _evtSource.onerror = (err) => {
    appendLog('SSE connection error — polling fallback…', 'log-err');
    _evtSource.close();
    pollStatus(jobId);
  };
}

function pollStatus(jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/status/${jobId}`);
      const data = await res.json();
      // Show only new logs
      const box = document.getElementById('logBox');
      const shown = box.querySelectorAll('.log-line').length;
      data.logs.slice(shown).forEach(l => appendLog(l));
      if (data.status !== 'running') {
        clearInterval(interval);
        clearInterval(_elapsedTimer);
        if (data.result && !data.result.error) {
          setBadge('done');
          showResult(data.result);
        } else {
          setBadge('error');
        }
        document.getElementById('submitBtn').disabled = false;
      }
    } catch (_) {}
  }, 3000);
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def ui():
    return HTMLResponse(_HTML)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")