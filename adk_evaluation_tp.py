"""
adk_evaluation_tp.py

- Reads test_cases.xlsx with columns: query, expected_output, expected_sql
- Calls local ADK at BASE_URL /run
- Extracts generated_output, generated_sql, generated_meta
- Canonicalizes both expected and generated SQL (sqlglot + GROUP BY ordinal expansion)
- Compares SQL: exact canonical equality -> structural set-equality -> embedding similarity (fallback)
- PASS only if text similarity >= OUTPUT_SIM_THRESHOLD AND SQL check passes
- Writes results to evaluation_results.xlsx
"""

import json
import re
import uuid
import requests
import pandas as pd
from sentence_transformers import SentenceTransformer, util

# ------------------------
# Config
# ------------------------
BASE_URL = "http://127.0.0.1:8000"
APP_NAME = "data_science"
USER_ID = "user"

INPUT_FILE = "test_cases_tp.xlsx"       # must have columns: query, expected_output, expected_sql
OUTPUT_FILE = "evaluation_results_tp.xlsx"

OUTPUT_SIM_THRESHOLD = 0.80
SQL_SIM_THRESHOLD = 0.95   # used only as fallback when canonical/structural checks fail

REQUEST_TIMEOUT = 1000

# ------------------------
# Init embedding model
# ------------------------
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")


def compute_similarity(a, b):
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
# Helpers: code fence strip + top-level comma split
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
# Lightweight structural equality (select/group sets)
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
# Extractor (final text, last SQL candidate, chart_meta)
# ------------------------
def try_parse_json_string(s: str):
    if not isinstance(s, str):
        return None
    cleaned = strip_code_fences(s)
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def extract_output(resp_json):
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

    def scan_part(p):
        if not isinstance(p, dict):
            return
        t = p.get("text")
        if isinstance(t, str) and t.strip():
            content_texts.append(strip_code_fences(t.strip()))
        fr = p.get("functionResponse")
        if isinstance(fr, dict):
            resp_obj = fr.get("response")
            if isinstance(resp_obj, dict):
                for tk in ("nl_results", "explain", "text", "result"):
                    if isinstance(resp_obj.get(tk), str) and resp_obj.get(tk).strip():
                        funcresp_texts.append(strip_code_fences(resp_obj.get(tk).strip()))
                        break
                if isinstance(resp_obj.get("sql"), str) and resp_obj.get("sql").strip():
                    sql_candidates.append(resp_obj.get("sql").strip())
            elif isinstance(resp_obj, str):
                parsed = try_parse_json_string(resp_obj)
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("sql"), str) and parsed.get("sql").strip():
                        sql_candidates.append(parsed.get("sql").strip())
                    for tk in ("nl_results", "explain", "text", "result"):
                        if isinstance(parsed.get(tk), str) and parsed.get(tk).strip():
                            funcresp_texts.append(parsed.get(tk).strip())
                            break
                for m in SELECT_RE.finditer(resp_obj):
                    sql_candidates.append(m.group(1).strip())
                if not sql_candidates and resp_obj.strip():
                    funcresp_texts.append(strip_code_fences(resp_obj.strip()))
        for k in ("chart_type", "x_axis_label", "y_axis_label"):
            if result["chart_meta"].get(k) is None and isinstance(p.get(k), str):
                result["chart_meta"][k] = p.get(k)

    def scan_state(sd):
        if not isinstance(sd, dict):
            return
        for tk in ("db_agent_output", "dv_agent_output", "nl_results", "explain"):
            if isinstance(sd.get(tk), str) and sd.get(tk).strip():
                sd_texts.append(strip_code_fences(sd.get(tk).strip()))
        if isinstance(sd.get("sql_query"), str) and sd.get("sql_query").strip():
            sql_candidates.append(sd.get("sql_query").strip())
        for k in ("chart_type", "x_axis_label", "y_axis_label"):
            if result["chart_meta"].get(k) is None and sd.get(k) is not None:
                result["chart_meta"][k] = sd.get(k)

    if isinstance(resp_json, dict):
        actions = resp_json.get("actions") or {}
        scan_state(actions.get("stateDelta") or {})
        if "content" in resp_json:
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

    if not sql_candidates:
        for m in SELECT_RE.finditer(raw_str):
            sql_candidates.append(m.group(1).strip())

    if content_texts:
        result["result_text"] = content_texts[-1]
    elif sd_texts:
        result["result_text"] = sd_texts[-1]
    elif funcresp_texts:
        result["result_text"] = funcresp_texts[-1]
    else:
        snippet = raw_str
        if len(snippet) > 2000:
            snippet = snippet[:2000] + "..."
        result["result_text"] = snippet

    if sql_candidates:
        result["sql"] = sql_candidates[-1]

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
        session_id = resp.json().get("id") or str(uuid.uuid4())
        return session_id
    except Exception as e:
        print(f"Session create failed, using fallback UUID: {e}")
        return str(uuid.uuid4())


# ------------------------
# Main loop
# ------------------------
print(f"Reading test cases from {INPUT_FILE}...")
df = pd.read_excel(INPUT_FILE)

required_cols = {"query", "expected_output", "expected_sql"}
if not required_cols.issubset(set(df.columns)):
    raise ValueError(f"Input Excel must have columns: {', '.join(required_cols)}")

generated_texts = []
generated_sqls = []
generated_meta_list = []
output_similarities = []
sql_similarities = []
statuses = []
raw_responses = []

print("Running evaluation...")

for idx, row in df.iterrows():
    query = row["query"]
    expected_output = row["expected_output"]
    expected_sql = row["expected_sql"]

    session_id = create_session()

    gen_text = None
    gen_sql = None
    gen_meta = {"chart_type": None, "x_axis_label": None, "y_axis_label": None}
    raw_resp_str = None

    try:
        payload = {
            "appName": APP_NAME,
            "userId": USER_ID,
            "sessionId": session_id,
            "newMessage": {
                "parts": [{"text": query}],
                "role": "user"
            },
            "streaming": False
        }
        resp = requests.post(f"{BASE_URL}/run", json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp_json = resp.json()
        raw_resp_str = json.dumps(resp_json, default=str)
        parsed = extract_output(resp_json)
        gen_text = parsed.get("result_text")
        gen_sql = parsed.get("sql")
        gen_meta = parsed.get("chart_meta") or gen_meta

    except Exception as e:
        gen_text = f"Error: {e}"
        gen_sql = None
        gen_meta = {"chart_type": None, "x_axis_label": None, "y_axis_label": None}
        raw_resp_str = str(e)

    # Text similarity (unchanged)
    out_sim = compute_similarity(expected_output, gen_text)

    # SQL comparison: canonicalize both expected and generated statements
    expected_canon = canonicalize_sql(expected_sql)
    gen_canon = canonicalize_sql(gen_sql)

    sql_equal = False
    sql_sim = 0.0

    # 1) exact canonical equality
    if expected_canon and gen_canon and expected_canon == gen_canon:
        sql_equal = True
        sql_sim = 1.0
    else:
        # 2) structural set-equality (select & group-by sets)
        try:
            if sql_structural_equal(expected_sql, gen_sql):
                sql_equal = True
                sql_sim = 1.0
        except Exception:
            pass
        # 3) fallback embedding similarity on canonical strings
        if not sql_equal:
            if expected_canon and gen_canon:
                sql_sim = compute_similarity(expected_canon, gen_canon)
            else:
                sql_sim = 0.0

    sql_ok = sql_equal or (sql_sim >= SQL_SIM_THRESHOLD)
    status = "PASS" if (out_sim >= OUTPUT_SIM_THRESHOLD and sql_ok) else "FAIL"

    save_text = strip_code_fences(gen_text) if isinstance(gen_text, str) else gen_text
    generated_texts.append(save_text)
    generated_sqls.append(gen_sql)
    generated_meta_list.append(json.dumps(gen_meta, ensure_ascii=False))
    output_similarities.append(round(out_sim, 4))
    sql_similarities.append(round(sql_sim, 4))
    statuses.append(status)
    raw_responses.append(raw_resp_str)

    print(f"[{status}] idx={idx} | out_sim={out_sim:.3f} sql_sim={sql_sim:.3f} | query={str(query)[:80]}")

# Save results
df["generated_output"] = generated_texts
df["generated_sql"] = generated_sqls
df["generated_meta"] = generated_meta_list
df["output_similarity"] = output_similarities
df["sql_similarity"] = sql_similarities
df["status"] = statuses
df["raw_response"] = raw_responses

df.to_excel(OUTPUT_FILE, index=False)
print(f"\nEvaluation completed. Results saved to {OUTPUT_FILE}")
