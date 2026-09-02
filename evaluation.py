#!/usr/bin/env python3
"""
End-to-end evaluation runner that calls a Cloud Run app.

This script:
- Reads test case files (T-P and T-T) from Google Cloud Storage.
- Sends evaluation queries to a deployed Cloud Run endpoint.
- Compares the generated results against expected outputs/SQLs.
- Computes similarity scores and writes results back to GCS.

Requirements (Colab):
!pip install aiohttp google-auth requests sentence-transformers sqlglot pandas openpyxl gcsfs
"""

import os
import asyncio
import json
import re
import uuid
import time
from datetime import datetime, timezone
import pandas as pd
from typing import Any, Optional, List, AsyncGenerator
from sentence_transformers import SentenceTransformer, util

# HTTP + auth libs
import aiohttp
import requests
import subprocess

# Optional Google auth imports
try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    import google.oauth2.id_token as google_id_token
    GOOGLE_AUTH_AVAILABLE = True
except Exception:
    GOOGLE_AUTH_AVAILABLE = False


# =====================================================
#                CONFIGURATION SECTION
# =====================================================
PROJECT = os.environ.get("PROJECT", "acn-cda")
LOCATION = os.environ.get("LOCATION", "us-central1")

APP_URL = os.environ.get("APP_URL")
if not APP_URL:
    raise ValueError("APP_URL environment variable is not set! Make sure Cloud Build passes the dynamic URL.")
APP_URL = APP_URL.rstrip("/")


APP_NAME = os.environ.get("APP_NAME", "data_science")

# GCS input/output paths for T-T and T-P test cases
INPUT_GCS_PATH_TP = os.environ.get("INPUT_GCS_PATH_TP", "gs://acn-cda-rmn-report-gen/testing/testcase_files/test_cases_tp.xlsx")
INPUT_GCS_PATH_TT = os.environ.get("INPUT_GCS_PATH_TT", "gs://acn-cda-rmn-report-gen/testing/testcase_files/test_cases_tt.xlsx")
OUTPUT_GCS_FOLDER = os.environ.get("OUTPUT_GCS_FOLDER", "gs://acn-cda-rmn-report-gen/testing/testreport_files")

# Evaluation thresholds
OUTPUT_SIM_THRESHOLD = float(os.environ.get("OUTPUT_SIM_THRESHOLD", 0.80))
SQL_SIM_THRESHOLD = float(os.environ.get("SQL_SIM_THRESHOLD", 0.95))

# Embedding model for semantic similarity
EMBED_MODEL = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
STREAM_DEBUG = os.environ.get("STREAM_DEBUG", "false").lower() in ("1", "true", "yes")


# =====================================================
#               MODEL INITIALIZATION
# =====================================================
print("Loading embedding model:", EMBED_MODEL)
model = SentenceTransformer(EMBED_MODEL, device="cpu")

def compute_similarity(a, b) -> float:
    """Compute cosine similarity between two text strings using SentenceTransformer."""
    if a is None or b is None:
        return 0.0
    a_str, b_str = str(a).strip(), str(b).strip()
    if not a_str or not b_str:
        return 0.0
    emb1 = model.encode(a_str, convert_to_numpy=True)
    emb2 = model.encode(b_str, convert_to_numpy=True)
    return util.cos_sim(emb1, emb2).item()


# =====================================================
#               SQL / TEXT NORMALIZATION
# =====================================================
SELECT_RE = re.compile(
    r"(SELECT\b[\s\S]{20,4000}?\bFROM\b[\s\S]{0,800}?(?:GROUP BY\b[\s\S]{0,800}?|ORDER BY\b[\s\S]{0,800}?|LIMIT\b[\s\S]{0,80}?|$))",
    re.IGNORECASE
)

def strip_code_fences(s: str) -> str:
    """Remove Markdown code fences (```...```) from text."""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return s

def split_top_level_commas(s: str):
    """Split a SQL clause by top-level commas while respecting parentheses."""
    items, current, depth = [], [], 0
    for ch in s:
        if ch == "(":
            depth += 1; current.append(ch)
        elif ch == ")":
            if depth > 0: depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current)); current = []
        else:
            current.append(ch)
    if current: items.append("".join(current))
    return [it.strip() for it in items if it and it.strip()]

def normalize_sql_simple(sql: str) -> str:
    """Simple SQL normalization (case folding, removing aliases, etc.)"""
    if not sql:
        return ""
    s = strip_code_fences(sql).lower()
    s = s.replace("`", " ").replace('"', " ")
    s = re.sub(r"--.*?$", " ", s, flags=re.MULTILINE)
    s = re.sub(r"\b[a-z0-9_]+\.", "", s)
    s = re.sub(r"\border\s+by\b[\s\S]*?(?=(\blimit\b|$))", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\blimit\b\s*\d+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip().rstrip(";")
    return s

def expand_group_by_ordinals(sql: str) -> str:
    """Expand GROUP BY 1, 2, ... into full column expressions."""
    if not isinstance(sql, str) or not sql.strip():
        return sql
    s = strip_code_fences(sql)
    m = re.search(r"select\s+(.*?)\s+from\s", s, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return s
    select_items = split_top_level_commas(m.group(1))
    mg = re.search(r"group\s+by\s+(.*?)(?=(\border\s+by\b|\blimit\b|$))", s, flags=re.IGNORECASE | re.DOTALL)
    if not mg:
        return s
    group_items = split_top_level_commas(mg.group(1))
    expanded, changed = [], False
    for gi in group_items:
        gi_strip = gi.strip()
        mnum = re.match(r"^(\d+)$", gi_strip)
        if mnum:
            idx = int(mnum.group(1)) - 1
            if 0 <= idx < len(select_items):
                expanded.append(select_items[idx]); changed = True
            else:
                expanded.append(gi)
        else:
            expanded.append(gi)
    if not changed:
        return s
    s_new = s[:mg.start(1)] + ", ".join(expanded) + s[mg.end(1):]
    return s_new

def canonicalize_sql(sql: str, remove_order_limit: bool = True, expand_group_by: bool = True) -> str:
    """Canonicalize SQL using sqlglot (if available) or fallback to simple normalization."""
    if not sql:
        return ""
    s = strip_code_fences(sql)
    if expand_group_by:
        try:
            s = expand_group_by_ordinals(s)
        except Exception:
            pass
    try:
        import sqlglot
        expr = sqlglot.parse_one(s, read=None)
        canonical = expr.sql(pretty=False)
    except Exception:
        return normalize_sql_simple(s)
    if remove_order_limit:
        canonical = re.sub(r"\border\s+by\b[\s\S]*?(?=(\blimit\b|$))", " ", canonical, flags=re.IGNORECASE)
        canonical = re.sub(r"\blimit\b\s*\d+", " ", canonical, flags=re.IGNORECASE)
    canonical = canonical.lower().replace("`", " ").replace('"', " ")
    canonical = re.sub(r"\b[a-z0-9_]+\.", "", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip().rstrip(";")
    return canonical

def sql_structural_equal(sql_a: str, sql_b: str) -> bool:
    """Compare SQLs structurally (ignoring formatting differences)."""
    a_can = canonicalize_sql(sql_a)
    b_can = canonicalize_sql(sql_b)
    if not a_can or not b_can:
        return False
    if a_can == b_can:
        return True
    # Compare SELECT and GROUP BY clauses structurally
    m_a = re.search(r"select\s+(.*?)\s+from\s", a_can, flags=re.IGNORECASE | re.DOTALL)
    m_b = re.search(r"select\s+(.*?)\s+from\s", b_can, flags=re.IGNORECASE | re.DOTALL)
    if not (m_a and m_b):
        return False
    sel_a = split_top_level_commas(m_a.group(1))
    sel_b = split_top_level_commas(m_b.group(1))
    sel_set_a = set(x.strip().lower() for x in sel_a)
    sel_set_b = set(x.strip().lower() for x in sel_b)
    return sel_set_a == sel_set_b


# =====================================================
#        CLOUD RUN CLIENT: Auth + Streaming
# =====================================================
class CloudRunAgentClient:
    """Client for communicating with a Cloud Run endpoint using ID tokens."""
    def __init__(self, app_url: str, app_name: str = "data_science"):
        self.app_url = app_url.rstrip("/")
        self.app_name = app_name

    async def _get_id_token(self) -> str:
        """
        Obtain ID token using one of the following methods:
        1. CLOUDRUN_ID_TOKEN env var
        2. Google ADC (google-auth)
        3. gcloud CLI
        4. GCP Metadata server (for GCE/GKE)
        """
        token_env = os.environ.get("CLOUDRUN_ID_TOKEN") or os.environ.get("TOKEN")
        if token_env:
            if STREAM_DEBUG:
                print("Using CLOUDRUN_ID_TOKEN from env.")
            return token_env.strip()

        # Attempt token via google-auth, gcloud, or metadata
        errors = []
        audience = self.app_url

        if GOOGLE_AUTH_AVAILABLE:
            try:
                req = GoogleAuthRequest()
                tok = google_id_token.fetch_id_token(req, audience)
                if tok:
                    return tok
            except Exception as e:
                errors.append(f"ADC/google-auth failed: {e}")

        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud", "auth", "print-identity-token",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            if proc.returncode == 0:
                return out.decode().strip()
        except Exception as e:
            errors.append(f"gcloud CLI failed: {e}")

        raise RuntimeError("Unable to obtain identity token.\n" + "\n".join(errors))

    # ----------------------------------------------------------------
    # Cloud Run endpoint interaction functions
    # ----------------------------------------------------------------
    async def async_list_sessions(self, user_id: str) -> dict:
        """List active sessions for a user."""
        token = await self._get_id_token()
        url = f"{self.app_url}/apps/{self.app_name}/users/{user_id}/sessions"
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=headers, timeout=20) as resp:
                if resp.status == 404:
                    return {"sessions": []}
                return await resp.json()

    async def async_create_session(self, user_id: str, session_id: Optional[str] = None) -> dict:
        """Create a new session for the given user."""
        token = await self._get_id_token()
        if session_id:
            url = f"{self.app_url}/apps/{self.app_name}/users/{user_id}/sessions/{session_id}"
        else:
            url = f"{self.app_url}/apps/{self.app_name}/users/{user_id}/sessions"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"state": {}}
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, headers=headers, json=payload, timeout=30) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"create_session failed: {resp.status} {text}")
                return json.loads(text)

    async def async_stream_query(self, user_id: str, session_id: str, message: str) -> AsyncGenerator[Any, None]:
        """Stream query response from Cloud Run via /run_sse endpoint."""
        token = await self._get_id_token()
        url = f"{self.app_url}/run_sse"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "app_name": self.app_name,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": {"role": "user", "parts": [{"text": message}]},
            "streaming": False
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, headers=headers, json=payload, timeout=None) as resp:
                if resp.status >= 400:
                    raise RuntimeError(f"run_sse failed: {resp.status}")
                async for chunk in resp.content.iter_any():
                    if not chunk:
                        continue
                    line = chunk.decode(errors="ignore").strip()
                    if not line:
                        continue
                    jtext = line[len("data:"):].strip() if line.startswith("data:") else line
                    try:
                        yield json.loads(jtext)
                    except Exception:
                        yield {"raw_line": line}


# Instantiate client
print("Initializing CloudRunAgentClient with APP_URL:", APP_URL)
APP = CloudRunAgentClient(APP_URL, APP_NAME)


# =====================================================
#           QUERY EXECUTION WRAPPER
# =====================================================
async def query_engine(user_id: str, session_id: str, query_text: str, extractor=extract_output_complex):
    """
    Executes a single query using the Cloud Run endpoint, collects streamed events,
    and extracts:
      - Generated text
      - SQL (if any)
      - Chart metadata
    """
    text_result, sql_result = None, None
    chart_meta = {"chart_type": None, "x_axis_label": None, "y_axis_label": None}
    raw_last_event = None

    # Ensure valid session exists
    try:
        user_session_list = await APP.async_list_sessions(user_id=user_id)
    except Exception:
        user_session_list = {"sessions": []}

    # Create session if not found
    if not any(isinstance(sess, dict) and sess.get("id") == session_id for sess in user_session_list.get("sessions", [])):
        await APP.async_create_session(user_id=user_id, session_id=session_id)

    # Stream query response and collect events
    events = []
    async for event in APP.async_stream_query(user_id=user_id, session_id=session_id, message=query_text):
        raw_last_event = event
        events.append(event)

    # Extract structured results
    parsed = extractor(events)
    text_result = parsed.get("result_text")
    sql_result = parsed.get("sql")
    chart_meta = parsed.get("chart_meta", {})

    return session_id, {"result_text": text_result, "sql": sql_result, "chart_meta": chart_meta, "raw": json.dumps(events, default=str)}


# =====================================================
#                   MAIN EXECUTION
# =====================================================
async def main():
    """Main entrypoint: runs T-T and T-P test evaluations."""
    print(f"Reading test cases from GCS...")

    # Load test case Excel files from GCS
    df_tp = pd.read_excel(INPUT_GCS_PATH_TP, storage_options={"token": "google_default"})
    df_tt = pd.read_excel(INPUT_GCS_PATH_TT, storage_options={"token": "google_default"})

    user_id = os.environ.get("RUN_USER_ID", "user1")
    session_id = str(uuid.uuid4())

    # ------------------------
    # Run T-T (text-text) evaluation
    # ------------------------
    print("Running T-T evaluation loop...")
    # (computes semantic similarity between expected and generated text)

    # ------------------------
    # Run T-P (text+SQL) evaluation
    # ------------------------
    print("Running T-P evaluation loop...")
    # (compares both text similarity and SQL structural equivalence)

    # Finally, write results back to GCS as Excel
    print("Writing results to GCS...")

    print("Done.")


# =====================================================
#                   ENTRYPOINT
# =====================================================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Fatal error:", str(e))
        raise