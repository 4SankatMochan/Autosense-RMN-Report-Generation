"""
adk_evaluation_tp.py

End-to-end evaluation harness (configured for your environment).

- Reads INPUT_FILE (Excel) which must contain columns:
    - query
    - expected_output
    - expected_sql

- Calls local ADK at BASE_URL /run using APP_NAME and USER_ID provided below.
- Extracts:
    - generated_output  (final human-facing text from the agent)
    - generated_sql     (last SQL candidate produced by the agent)
    - generated_meta    (chart metadata: chart_type, x_axis_label, y_axis_label)

- SQL handling:
    - Canonicalizes both expected_sql and generated_sql using sqlglot (best-effort).
    - Expands GROUP BY ordinals (e.g., GROUP BY 1) into corresponding SELECT expressions before canonicalization.
    - Comparison order:
        1) exact canonical equality
        2) lightweight structural equality (select-set and group-by-set)
        3) fallback embedding similarity on canonical SQL strings (threshold SQL_SIM_THRESHOLD)

- Text similarity for generated output is computed with sentence-transformers.
- PASS only if:
    - text similarity >= OUTPUT_SIM_THRESHOLD AND
    - SQL check passes (canonical/structural equality OR fallback similarity >= SQL_SIM_THRESHOLD)

- Timing:
    - records request_time (UTC, ISO with Z), response_time (UTC, ISO with Z), and latency_mmss (M:SS.mmm)

Configuration values (update these if needed):
    BASE_URL, APP_NAME, USER_ID
    INPUT_FILE, OUTPUT_FILE
    OUTPUT_SIM_THRESHOLD, SQL_SIM_THRESHOLD
    REQUEST_TIMEOUT (seconds)

Dependencies:
    pip install sqlglot sentence-transformers requests openpyxl
"""

import json
import re
import uuid
import time
import datetime
import requests
import pandas as pd
from sentence_transformers import SentenceTransformer, util

# ------------------------
# Config (your provided working values)
# ------------------------
BASE_URL = "http://127.0.0.1:8000"
APP_NAME = "data_science"
USER_ID = "user"

INPUT_FILE = "test_cases_tp.xlsx"       # must have columns: query, expected_output, expected_sql
OUTPUT_FILE = "evaluation_results_tp.xlsx"

OUTPUT_SIM_THRESHOLD = 0.80
SQL_SIM_THRESHOLD = 0.95   # used only as fallback when canonical/structural checks fail

REQUEST_TIMEOUT = 1000  # seconds

# ------------------------
# Init embedding model
# ------------------------
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")


def compute_similarity(a, b):
    """Compute semantic similarity between two texts using sentence-transformers."""
    if a is None or b is None:
        return 0.0
    a_str = str(a).strip()
    b_str = str(b).strip()
    if not a_str or not b_str:
        return 0.0
    emb1 = model.encode(a_str, convert_to_tensor=True)
    emb2 = model.encode(b_str, convert_to_tensor=True)
    return util.cos_sim(emb1, emb2).item()


# ------------------------
# Helpers: strip code fences + split top-level commas
# ------------------------
def strip_code_fences(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return s


def split_top_level_commas(s: str):
    items = []
    current = []
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            if depth > 0:
                depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        items.append("".join(current))
    return [it.strip() for it in items if it and it.strip()]


# ------------------------
# SQL canonicalization + GROUP BY ordinal expansion
# ------------------------
SELECT_RE = re.compile(
    r"(SELECT\b[\s\S]{20,4000}?\bFROM\b[\s\S]{0,800}?(?:GROUP BY\b[\s\S]{0,800}?|ORDER BY\b[\s\S]{0,800}?|LIMIT\b[\s\S]{0,80}?|$))",
    re.IGNORECASE
)


def normalize_sql_simple(sql: str) -> str:
    """Conservative fallback normalization for SQL if sqlglot is unavailable or parse fails."""
    if not sql:
        return ""
    s = strip_code_fences(sql)
    s = s.lower()
    s = s.replace("`", " ").replace('"', " ")
    s = re.sub(r"--.*?$", " ", s, flags=re.MULTILINE)
    s = re.sub(r"\b[a-z0-9_]+\.", "", s)
    s = re.sub(r"\border\s+by\b[\s\S]*?(?=(\blimit\b|$))", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\blimit\b\s*\d+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip().rstrip(";")
    return s


def expand_group_by_ordinals(sql: str) -> str:
    """
    Expand `GROUP BY 1,2` ordinals into the corresponding SELECT expressions.
    If expansion cannot be performed, returns original SQL unchanged.
    """
    if not isinstance(sql, str) or not sql.strip():
        return sql
    s = strip_code_fences(sql)
    m = re.search(r"select\s+(.*?)\s+from\s", s, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return s
    select_list = m.group(1)
    select_items = split_top_level_commas(select_list)
    if not select_items:
        return s
    mg = re.search(r"group\s+by\s+(.*?)(?=(\border\s+by\b|\blimit\b|$))", s, flags=re.IGNORECASE | re.DOTALL)
    if not mg:
        return s
    group_body = mg.group(1)
    group_items = split_top_level_commas(group_body)
    expanded_items = []
    changed = False
    for gi in group_items:
        gi_strip = gi.strip()
        mnum = re.match(r"^(\d+)$", gi_strip)
        if mnum:
            idx = int(mnum.group(1)) - 1
            if 0 <= idx < len(select_items):
                expanded_items.append(select_items[idx])
                changed = True
            else:
                expanded_items.append(gi)
        else:
            expanded_items.append(gi)
    if not changed:
        return s
    new_group = ", ".join(expanded_items)
    s_new = s[:mg.start(1)] + new_group + s[mg.end(1):]
    return s_new


def canonicalize_sql(sql: str, remove_order_limit: bool = True, expand_group_by: bool = True) -> str:
    """
    Canonicalize SQL using sqlglot where possible. Falls back to normalize_sql_simple on failure.
    """
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
    except Exception:
        return normalize_sql_simple(s)
    try:
        expr = sqlglot.parse_one(s, read=None)
    except Exception:
        return normalize_sql_simple(s)
    try:
        canonical = expr.sql(pretty=False)
    except Exception:
        return normalize_sql_simple(s)
    if remove_order_limit:
        canonical = re.sub(r"\border\s+by\b[\s\S]*?(?=(\blimit\b|$))", " ", canonical, flags=re.IGNORECASE)
        canonical = re.sub(r"\blimit\b\s*\d+", " ", canonical, flags=re.IGNORECASE)
    canonical = canonical.lower()
    canonical = canonical.replace("`", " ").replace('"', " ")
    canonical = re.sub(r"\b[a-z0-9_]+\.", "", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip().rstrip(";")
    return canonical


# ------------------------
# Lightweight structural equality (select & group-by sets)
# ------------------------
def normalize_expr_for_set(expr: str) -> str:
    if not expr:
        return ""
    s = expr.strip()
    while s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    s = re.sub(r"\s+as\s+\w+$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+\w+$", "", s)  # trailing alias e.g., "expr alias"
    s = re.sub(r"\b[a-zA-Z0-9_]+\.", "", s)  # remove qualifiers
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def sql_structural_equal(sql_a: str, sql_b: str) -> bool:
    """Return True if select-set and group-by-set (normalized) are equal, else False."""
    a_can = canonicalize_sql(sql_a)
    b_can = canonicalize_sql(sql_b)
    if not a_can or not b_can:
        return False
    if a_can == b_can:
        return True
    m_a = re.search(r"select\s+(.*?)\s+from\s", a_can, flags=re.IGNORECASE | re.DOTALL)
    m_b = re.search(r"select\s+(.*?)\s+from\s", b_can, flags=re.IGNORECASE | re.DOTALL)
    if not (m_a and m_b):
        return False
    sel_a = split_top_level_commas(m_a.group(1))
    sel_b = split_top_level_commas(m_b.group(1))
    sel_set_a = set(normalize_expr_for_set(x) for x in sel_a)
    sel_set_b = set(normalize_expr_for_set(x) for x in sel_b)
    mg_a = re.search(r"group\s+by\s+(.*?)(?=(\border\s+by\b|\blimit\b|$))", a_can, flags=re.IGNORECASE | re.DOTALL)
    mg_b = re.search(r"group\s+by\s+(.*?)(?=(\border\s+by\b|\blimit\b|$))", b_can, flags=re.IGNORECASE | re.DOTALL)
    if mg_a and mg_b:
        grp_a = split_top_level_commas(mg_a.group(1))
        grp_b = split_top_level_commas(mg_b.group(1))
        grp_set_a = set(normalize_expr_for_set(x) for x in grp_a)
        grp_set_b = set(normalize_expr_for_set(x) for x in grp_b)
    else:
        if mg_a or mg_b:
            return False
        grp_set_a = grp_set_b = set()
    return sel_set_a == sel_set_b and grp_set_a == grp_set_b


# ------------------------
# Improved Extractor: prefer last human-facing text, last SQL candidate, and chart meta
# ------------------------
def extract_output(resp_json):
    """
    Improved extractor:
      - scans actions.stateDelta for sql_query and nl_results/explain
      - scans content.parts[*] for text and functionResponse
      - handles functionResponse.response as dict and as code-fenced JSON string
      - returns last discovered SQL candidate and last discovered human text
    """
    result = {
        "result_text": None,
        "sql": None,
        "chart_meta": {"chart_type": None, "x_axis_label": None, "y_axis_label": None},
        "raw": None
    }

    try:
        raw_str = json.dumps(resp_json, default=str)
    except Exception:
        raw_str = str(resp_json)
    result["raw"] = raw_str

    content_texts = []
    sd_texts = []
    funcresp_texts = []
    sql_candidates = []

    def try_parse_json_string(s: str):
        if not isinstance(s, str):
            return None
        cleaned = strip_code_fences(s)
        try:
            return json.loads(cleaned)
        except Exception:
            # try to find JSON substring inside
            m = re.search(r"(\{[\s\S]*\})", cleaned)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    return None
            return None

    def scan_state(sd: dict):
        if not isinstance(sd, dict):
            return
        # common state keys that may contain SQL or user-friendly text
        for tk in ("sql_query", "db_agent_output", "dv_agent_output", "nl_results", "explain"):
            v = sd.get(tk)
            if isinstance(v, str) and v.strip():
                if tk == "sql_query":
                    sql_candidates.append(v.strip())
                else:
                    sd_texts.append(strip_code_fences(v.strip()))
        # chart metadata in stateDelta
        for k in ("chart_type", "x_axis_label", "y_axis_label"):
            if result["chart_meta"].get(k) is None and sd.get(k) is not None:
                result["chart_meta"][k] = sd.get(k)

    def scan_part(p: dict):
        if not isinstance(p, dict):
            return
        # plain text content
        t = p.get("text")
        if isinstance(t, str) and t.strip():
            content_texts.append(strip_code_fences(t.strip()))

        # functionResponse handling
        fr = p.get("functionResponse")
        if isinstance(fr, dict):
            resp_obj = fr.get("response")
            # response is a dict with structured fields
            if isinstance(resp_obj, dict):
                # direct sql field
                if isinstance(resp_obj.get("sql"), str) and resp_obj.get("sql").strip():
                    sql_candidates.append(resp_obj.get("sql").strip())
                # check for textual fields (and JSON inside them)
                for tk in ("nl_results", "explain", "text", "result", "db_agent_output"):
                    val = resp_obj.get(tk)
                    if isinstance(val, str) and val.strip():
                        funcresp_texts.append(strip_code_fences(val.strip()))
                        parsed = try_parse_json_string(val)
                        if isinstance(parsed, dict) and isinstance(parsed.get("sql"), str):
                            sql_candidates.append(parsed.get("sql").strip())
            # response is a string (often code-fenced JSON)
            elif isinstance(resp_obj, str):
                parsed = try_parse_json_string(resp_obj)
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("sql"), str) and parsed.get("sql").strip():
                        sql_candidates.append(parsed.get("sql").strip())
                    for tk in ("nl_results", "explain", "text", "result"):
                        if isinstance(parsed.get(tk), str) and parsed.get(tk).strip():
                            funcresp_texts.append(parsed.get(tk).strip())
                            break
                # fallback: regex search for SELECT blocks
                for m in SELECT_RE.finditer(resp_obj):
                    sql_candidates.append(m.group(1).strip())
                if not sql_candidates and resp_obj.strip():
                    funcresp_texts.append(strip_code_fences(resp_obj.strip()))

        # extract chart metadata if present on a part
        for k in ("chart_type", "x_axis_label", "y_axis_label"):
            if result["chart_meta"].get(k) is None and isinstance(p.get(k), str):
                result["chart_meta"][k] = p.get(k)

    # resp_json may be dict or list; handle both
    if isinstance(resp_json, dict):
        actions = resp_json.get("actions") or {}
        scan_state(actions.get("stateDelta") or {})
        parts = resp_json.get("content", {}).get("parts", []) or []
        for p in parts:
            scan_part(p)
    elif isinstance(resp_json, list):
        for item in resp_json:
            if not isinstance(item, dict):
                continue
            actions = item.get("actions") or {}
            scan_state(actions.get("stateDelta") or {})
            parts = item.get("content", {}).get("parts", []) or []
            for p in parts:
                scan_part(p)

    # fallback: search entire raw JSON string for SELECT blocks if nothing found yet
    if not sql_candidates:
        for m in SELECT_RE.finditer(result["raw"] or ""):
            sql_candidates.append(m.group(1).strip())

    # choose final result_text preference: last content text > stateDelta > functionResponse > raw snippet
    if content_texts:
        result["result_text"] = content_texts[-1]
    elif sd_texts:
        result["result_text"] = sd_texts[-1]
    elif funcresp_texts:
        result["result_text"] = funcresp_texts[-1]
    else:
        snippet = (result["raw"] or "")
        if len(snippet) > 2000:
            snippet = snippet[:2000] + "..."
        result["result_text"] = snippet

    # pick last SQL candidate if any
    if sql_candidates:
        result["sql"] = sql_candidates[-1]

    # clean empty strings to None
    if isinstance(result["result_text"], str) and not result["result_text"].strip():
        result["result_text"] = None
    if isinstance(result["sql"], str) and not result["sql"].strip():
        result["sql"] = None
    for k in ("chart_type", "x_axis_label", "y_axis_label"):
        v = result["chart_meta"].get(k)
        if isinstance(v, str) and not v.strip():
            result["chart_meta"][k] = None

    return result


# ------------------------
# create_session helper
# ------------------------
def create_session():
    try:
        resp = requests.post(f"{BASE_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id") or str(uuid.uuid4())
    except Exception:
        return str(uuid.uuid4())


# ------------------------
# Main evaluation loop
# ------------------------
print(f"Reading test cases from {INPUT_FILE}...")
df = pd.read_excel(INPUT_FILE)

required_cols = {"query", "expected_output", "expected_sql"}
if not required_cols.issubset(df.columns):
    raise ValueError(f"Input Excel must have columns: {', '.join(required_cols)}")

generated_texts, generated_sqls, generated_meta_list = [], [], []
output_similarities, sql_similarities, statuses, raw_responses = [], [], [], []
request_times, response_times, latency_mmss_list = [], [], []

print("Running evaluation...")

for idx, row in df.iterrows():
    query, expected_output, expected_sql = row["query"], row["expected_output"], row["expected_sql"]
    session_id = create_session()

    # timestamps in UTC (timezone-aware) with Z suffix
    req_time_epoch = time.time()
    req_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    try:
        payload = {
            "appName": APP_NAME,
            "userId": USER_ID,
            "sessionId": session_id,
            "newMessage": {"parts": [{"text": query}], "role": "user"},
            "streaming": False
        }
        resp = requests.post(f"{BASE_URL}/run", json=payload, timeout=REQUEST_TIMEOUT)

        resp_time_epoch = time.time()
        resp_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

        resp.raise_for_status()
        resp_json = resp.json()
        raw_resp_str = json.dumps(resp_json, default=str)
        parsed = extract_output(resp_json)
        gen_text, gen_sql, gen_meta = parsed.get("result_text"), parsed.get("sql"), parsed.get("chart_meta")

    except Exception as e:
        resp_time_epoch = time.time()
        resp_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        gen_text, gen_sql, gen_meta = f"Error: {e}", None, {}
        raw_resp_str = str(e)

    # compute latency (minutes:seconds.milliseconds)
    latency_secs = resp_time_epoch - req_time_epoch
    minutes, seconds = divmod(latency_secs, 60)
    latency_mmss = f"{int(minutes)}:{seconds:06.3f}"

    # Text similarity (generated output)
    out_sim = compute_similarity(expected_output, gen_text)

    # SQL comparison: canonicalize both statements and compare
    expected_canon = canonicalize_sql(expected_sql)
    gen_canon = canonicalize_sql(gen_sql)

    sql_equal, sql_sim = False, 0.0
    if expected_canon and gen_canon and expected_canon == gen_canon:
        sql_equal, sql_sim = True, 1.0
    elif sql_structural_equal(expected_sql, gen_sql):
        sql_equal, sql_sim = True, 1.0
    elif expected_canon and gen_canon:
        sql_sim = compute_similarity(expected_canon, gen_canon)

    sql_ok = sql_equal or (sql_sim >= SQL_SIM_THRESHOLD)
    status = "PASS" if (out_sim >= OUTPUT_SIM_THRESHOLD and sql_ok) else "FAIL"

    # save outputs
    generated_texts.append(strip_code_fences(gen_text) if isinstance(gen_text, str) else gen_text)
    generated_sqls.append(gen_sql)
    generated_meta_list.append(json.dumps(gen_meta, ensure_ascii=False))
    output_similarities.append(round(out_sim, 4))
    sql_similarities.append(round(sql_sim, 4))
    statuses.append(status)
    raw_responses.append(raw_resp_str)
    request_times.append(req_time_iso)
    response_times.append(resp_time_iso)
    latency_mmss_list.append(latency_mmss)

    print(f"[{status}] idx={idx} | out_sim={out_sim:.3f} sql_sim={sql_sim:.3f} latency={latency_mmss}")

# ------------------------
# Save results to Excel
# ------------------------
df["generated_output"] = generated_texts
df["generated_sql"] = generated_sqls
df["generated_meta"] = generated_meta_list
df["output_similarity"] = output_similarities
df["sql_similarity"] = sql_similarities
df["status"] = statuses
df["raw_response"] = raw_responses
df["request_time"] = request_times
df["response_time"] = response_times
df["latency_mmss"] = latency_mmss_list

df.to_excel(OUTPUT_FILE, index=False)
print(f"\nEvaluation completed. Results saved to {OUTPUT_FILE}")
