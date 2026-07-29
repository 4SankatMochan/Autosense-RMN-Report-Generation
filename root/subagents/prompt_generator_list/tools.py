import re
import os
import json
from datetime import datetime
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel
from pydantic import BaseModel,Field,TypeAdapter
from typing import Literal,List
from vertexai.generative_models import GenerationConfig
from .prompts import return_fusion_prompt
import time
class PromptList(BaseModel):
    section_name: Literal["Context","Campaign Overview","Campaign-wise Analysis"] = Field(...,description='Report section name')
    prompts: List[str] = Field(...,description='List of prompts')

output_schema=TypeAdapter(List[PromptList]).json_schema()

# ✅ Helper to safely parse bools
def _parse_bool(v, default=True):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    return default

# ✅ Helper to safely extract text from Gemini response
def safe_extract_text(response):
    try:
        if hasattr(response, "text"):
            return response.text.strip()
        if hasattr(response, "candidates") and response.candidates:
            return response.candidates[0].content.parts[0].text.strip()
        return str(response).strip()
    except Exception:
        return ""
    
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

def _normalize_text(s: str) -> str:
    """
    Lowercase, decode common HTML entities (&amp; → &), collapse punctuation and spaces.
    Also normalizes underscores/hyphens to spaces and trims.
    """
    if s is None:
        return ""
    s = s.replace("&amp;", "&")
    s = s.lower()
    # replace underscores/hyphens/slashes with spaces
    s = re.sub(r"[_/\-]+", " ", s)
    # keep alphanumerics and & only; convert the rest to spaces
    s = re.sub(r"[^a-z0-9&\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokenize(s: str) -> List[str]:
    return [t for t in _normalize_text(s).split() if t]

def _ratio(a: str, b: str) -> float:
    """Fallback similarity. If you have rapidfuzz, swap in token_set_ratio or partial_ratio."""
    return SequenceMatcher(None, a, b).ratio()

def _acronym(name: str) -> str:
    """
    Build a naive acronym: first letters of tokens ignoring short/common words.
    Example: 'Client Solution Manager' -> 'csm'
    """
    toks = _tokenize(name)
    toks = [t for t in toks if t not in {"and", "&", "of", "the"}]
    return "".join(t[0] for t in toks) if toks else ""

def resolve_persona(
    user_query: str,
    available_personas: List[str],
    persona_alias_map: Dict[str, List[str]] = None,
    min_conf_exact: float = 0.92,   # high threshold for near-exact
    min_conf_good: float = 0.80,    # good fuzzy match
    min_conf_ok: float = 0.68       # acceptable with token overlap / partial
) -> Dict[str, str]:
    """
    Returns: {"persona_name": <best match or None>, "score": <0..1>, "matched_alias": <alias or None>, "evidence": <why>}
    - Uses normalization, alias/acro matching, token overlap, containment, and fuzzy similarity.
    - Prefers exact/alias/acro matches; falls back to fuzzy.
    """
    uq_norm = _normalize_text(user_query)
    uq_tokens = set(_tokenize(user_query))

    # Build candidate rows: for each persona, include base name, aliases, acronym
    rows: List[Tuple[str, str, str]] = []  # (canonical_persona, candidate_variant, variant_type)
    for p in available_personas:
        # Decode HTML entities and normalize display name now
        p_disp = p.replace("&amp;", "&")
        variants = [p_disp]
        vtypes  = ["name"]

        # aliases
        if persona_alias_map and p in persona_alias_map:
            aliases = persona_alias_map[p] or []
            aliases = [a.replace("&amp;", "&") for a in aliases]
            variants.extend(aliases)
            vtypes.extend(["alias"] * len(aliases))

        # acronym
        acro = _acronym(p_disp)
        if acro:
            variants.append(acro)
            vtypes.append("acronym")

        for v, t in zip(variants, vtypes):
            rows.append((p_disp, v, t))

    # Score each candidate variant
    best = {"persona_name": None, "score": 0.0, "matched_alias": None, "evidence": ""}
    for canonical, variant, vtype in rows:
        v_norm = _normalize_text(variant)
        v_tokens = set(_tokenize(variant))

        score = 0.0
        evidence = []

        # 1) Exact normalized equality
        if v_norm and (v_norm == uq_norm):
            score = 1.0
            evidence.append("exact")
        # 2) Substring containment (user mentions the variant)
        elif v_norm and v_norm in uq_norm:
            score = 0.93
            evidence.append("substring")
        # 3) Token overlap Jaccard-ish
        elif v_tokens:
            inter = len(uq_tokens & v_tokens)
            union = len(uq_tokens | v_tokens)
            jacc = inter / union if union else 0.0
            # weight token overlap; scale a bit
            score = max(score, 0.70 + 0.20 * jacc) if inter else score
            if inter:
                evidence.append(f"token_overlap:{inter}/{union}")
        # 4) Fuzzy similarity as fallback
        sim = _ratio(v_norm, uq_norm) if v_norm else 0.0
        # combine (keep the strongest)
        score = max(score, sim)

        # Keep best by score; break ties preferring canonical name over alias/acronym
        if (score > best["score"]) or (abs(score - best["score"]) < 1e-6 and best["persona_name"] is None and vtype == "name"):
            best = {
                "persona_name": canonical,
                "score": float(score),
                "matched_alias": variant if vtype != "name" else None,
                "evidence": ",".join(evidence) if evidence else ("fuzzy" if sim == score else "")
            }

    # Apply confidence thresholds
    # Promote only if acceptable; otherwise return None to trigger disambiguation upstream.
    if best["score"] >= min_conf_exact:
        best["evidence"] = best["evidence"] or "near_exact"
        return best
    if best["score"] >= min_conf_good:
        best["evidence"] = best["evidence"] or "good_fuzzy"
        return best
    if best["score"] >= min_conf_ok:
        best["evidence"] = best["evidence"] or "ok_fuzzy"
        return best

    # Not confident — return None and score for upstream handling (e.g., propose top options)
    return {"persona_name": None, "score": float(best["score"]), "matched_alias": None, "evidence": "low_confidence"}

import re
import html

def build_brand_pattern(brands: List[str]) -> re.Pattern:
    """
    Build a regex that tolerates punctuation and '&'/'and' variation.
    We escape brand tokens and allow flexible separators between words.
    """
    def brand_to_pattern(b: str) -> str:
        b = html.unescape(b)
        # split into tokens; convert '&' to pattern (?:&|and)
        tokens = re.split(r"\s+", b.strip())
        patt_tokens = []
        for t in tokens:
            if t.lower() in {"&", "and"} or t == "&":
                patt_tokens.append(r"(?:&|and)")
            else:
                # allow internal punctuation variations
                t_escaped = re.escape(t).replace(r"\+", r"\+")
                # accept optional punctuation/spaces between letters (e.g., I.V. vs IV)
                t_escaped = re.sub(r"\\\.", r"[\.]?", t_escaped)
                patt_tokens.append(t_escaped)
        # allow flexible separators between tokens
        return r"\b" + r"\s*[-\s]*\s*".join(patt_tokens) + r"\b"

    alternates = [brand_to_pattern(b) for b in brands]
    full = "(?i)(" + "|".join(alternates) + ")"
    return re.compile(full)

import re
from datetime import datetime

def extract_explicit_time_period(user_query: str):
    result = {
        "start_date": "",
        "end_date": "",
        "type": ""
    }

    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }


    pattern = re.search(
        r"(?i)time_period\s*:\s*(\d{1,2})\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
        r"(\d{4})\s*[-–]\s*"
        r"(\d{1,2})\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
        r"(\d{4})",
        user_query
    )

    if not pattern:
        return result

    d1, m1, y1, d2, m2, y2 = pattern.groups()

    start = datetime(int(y1), month_map[m1[:3].lower()], int(d1))
    end = datetime(int(y2), month_map[m2[:3].lower()], int(d2))

    result["start_date"] = start.strftime("%Y-%m-%d")
    result["end_date"] = end.strftime("%Y-%m-%d")
    result["type"] = "range"

    return result

# Campaign objective–specific KPI templates (used for prompt generation)
# OBJECTIVE_KPIS = {
#     "Awareness": {
#         "Metrics_Table": {
#             "Channel": "",
#             "Total_Ad_Spend": "",
#             "Impressions": "",
#             "Reach": "",
#             "Frequency": "",
#             "ROAS": "",
#             "CPM": ""
#         }
#     },
#     "Consideration": {
#         "Metrics_Table": {
#             "Channel": "",
#             "Total_Ad_Spend": "",
#             "Impressions": "",
#             "Reach": "",
#             "Clicks": "",
#             "CTR": "",
#             "CPC": "",
#             "CPCV": "",
#             "Viewed_Units": "",
#             "Clicked_Units": "",
#             "Add_To_Cart": ""
#         }
#     },
#     "Conversion": {
#         "Metrics_Table": {
#             "Channel": "",
#             "Total_Ad_Spend": "",
#             "Impressions": "",
#             "Clicks": "",
#             "CTR": "",
#             "CPC": "",
#             "Viewed_Transactions": "",
#             "Clicked_Transactions": "",
#             "Viewed_Revenue": "",
#             "Clicked_Revenue": "",
#             "Total_Campaign_Revenue": "",
#             "ROAS": "",
#             "Incremental_Sales_Lift": "",
#             "Conversions": ""
#         }
#     },
#     "Retention": {
#         "Metrics_Table": {
#             "Channel": "",
#             "Total_Ad_Spend": "",
#             "Conversions": "",
#             "CVA": "",
#             "Transactions_Repeat": "",
#             "Units_Sold": "",
#             "Total_Campaign_Revenue": "",
#             "Incremental_Sales_Lift": "",
#             "ROAS": ""
#         }
#     },
# }

# Objective-specific KPIs (list of KPI names)
OBJECTIVE_KPIS = {
    "Awareness": ["Total_Ad_Spend", "Impressions", "Reach", "Frequency", "ROAS", "CPM"],
    "Consideration": ["Total_Ad_Spend", "Impressions", "Reach", "Clicks", "CTR", "CPC", "CPCV", "Viewed_Units", "Clicked_Units", "Add_To_Cart"],
    "Conversion": ["Total_Ad_Spend", "Impressions", "Clicks", "CTR", "CPC", "Viewed_Transactions", "Clicked_Transactions", "Viewed_Revenue", "Clicked_Revenue", "Total_Campaign_Revenue", "ROAS", "Incremental_Sales_Lift", "Conversions"],
    "Retention": ["Total_Ad_Spend", "Conversions", "CVA", "Transactions_Repeat", "Units_Sold", "Total_Campaign_Revenue", "Incremental_Sales_Lift", "ROAS"]
}

# OBJECTIVE_KPIS = {
# "Awareness": ["Channel_Total_Ad_Spend","Channel_Impressions","Channel_Unique_Reach","Channel_Frequency","Channel_ROAS","Channel_CPM"],
# "Consideration": ["Channel_Total_Ad_Spend","Channel_Impressions","Channel_Unique_Reach","Channel_Clicks","Channel_CTR","Channel_CPC","Channel_CPCV","Channel_Viewed_Units","Channel_Clicked_Units","Channel_Add_To_Cart"],
# "Conversion": ["Channel_Total_Ad_Spend","Channel_Impressions","Channel_Clicks","Channel_CTR","Channel_CPC","Channel_Viewed_Transactions","Channel_Clicked_Transactions","Channel_Viewed_Revenue","Channel_Clicked_Revenue","Channel_Total_Revenue","Channel_ROAS","Channel_Incremental_Sales_Lift","Channel_Conversions"],
# "Retention": ["Channel_Total_Ad_Spend","Channel_Conversions","Channel_CVR","Channel_Repeat_Transactions","Channel_Units_Sold","Channel_Total_Revenue","Channel_Incremental_Sales_Lift","Channel_ROAS"]
# }

def get_tone_and_kpis(personas, role, objective=None):
    # Find the persona
    persona_data = None
    for persona in personas:
        if persona.get("role") == role:
            persona_data = persona
            break
    
    if not persona_data:
        return None
    
    tone = persona_data.get("tone")
    
    # Determine relevant_kpis
    if objective and objective in OBJECTIVE_KPIS:
        relevant_kpis = OBJECTIVE_KPIS[objective][:8]  # limit to top 8 KPIs
    else:
        relevant_kpis = persona_data.get("relevant_kpis", [])[:8]  # limit to top 8 KPIs
    
    return {
        "tone": tone,
        "relevant_kpis": relevant_kpis
    }

async def generate_prompt(tool_context: ToolContext, **kwargs):
    """Generate structured Instruction + List of Prompts safely for Campaign Performance Report."""

    print(" Inside Prompt Generator Agent")
    session_id = getattr(tool_context._invocation_context.session, "id", "unknown_session")
    print(f"Session ID: {session_id}")

    # --- CONFIG ---
    use_gemini = _parse_bool(tool_context.state.get("use_gemini", True))
    temperature = float(tool_context.state.get("temperature", 0.02))
    model_name = (
        tool_context.state.get("generator_model")
        or os.getenv("SEQUENTIAL_AGENT")
        or "gemini-1.5-pro"
    )
    tool_context.state["modelused"] = model_name

    # 1️⃣ Extract user query
    user_query = str(tool_context.state.get("user_query", "")).strip()
    print(f"🧠 User Query: {user_query}")

    # 2️⃣ Load persona & persona_report safely (accepts dict OR list)
    persona_raw = tool_context.state.get("persona", "{}")
    persona_report_raw = tool_context.state.get("persona_report", "{}")
    # print(f"📂 Loaded persona (raw): {str(persona_raw)[:200]}...")
    # print(f"📂 Loaded persona_report (raw): {str(persona_report_raw)[:200]}...")

    def ensure_dict(obj):
        """Safely convert list/string to dict."""
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            try:
                return {item.get("persona") or item.get("name") or "Unknown": item for item in obj}
            except Exception:
                return {}
        if isinstance(obj, str):
            try:
                parsed = json.loads(obj)
                return ensure_dict(parsed)
            except Exception:
                return {}
        return {}

    persona_json = ensure_dict(persona_raw)
    persona_report_json = ensure_dict(persona_report_raw)

    # 3️⃣ Extract attributes (regex hardened to avoid N/A)
    available_personas = tool_context.state.get(
        "available_personas",
        ["Client Solution Manager", "Ad Ops Analyst","Ad Ops Manager","AI Engineer (Sell)", "Retail Media Owner", "Media & Campaign Manager_New","Brand Manager new","AI Engineer (Buy)"],
    )
    
    persona_alias_map = {
        "Client Solution Manager": ["Client Solutions Manager", "CSM", "Solutions Manager"],
        "Ad Ops Analyst": ["Ad Operations Analyst", "Advertising Ops Analyst"],
        "Ad Ops Manager": ["Ad Operations Manager", "AdOps Manager"],
        "AI Engineer (Sell)": ["AI Engineer Sell", "AI Sell Engineer"],
        "AI Engineer (Buy)": ["AI Engineer Buy", "AI Buy Engineer"],
        "Retail Media Owner": ["RMO", "Retail Media Lead", "Retail Media"],
        "Media & Campaign Manager_New": ["Media and Campaign Manager", "Media & Campaign Manager", "Campaign Manager"],
        "Brand Manager new": ["Brand Manager", "BM"],
    }

    persona_res = resolve_persona(user_query, available_personas, persona_alias_map)

    if persona_res["persona_name"]:
        persona_name = persona_res["persona_name"]
    else:
        # keep your default, but also surface top suggestions upstream (optional: compute top 3 by score)
        persona_name = tool_context.state.get("default_persona", "Media & Campaign Manager_New")

    # brand_match = re.search(r"(?i)\bfor\s+([A-Za-z0-9&\-\s]+?)\s+(?:brand|product)\b", user_query)

    """ Get brand names mentioned in the user query using regex pattern matching. The pattern is built to be flexible with punctuation and conjunctions. 
    """

    RAW_BRANDS = [
        "Axe", "Baby Dove", "Ben & Jerry's", "Brooke Bond", "Cif", "Clear", "Comfort",
        "Continental", "Cornetto", "Dermalogica", "Dollar Shave Club", "Domestos", "Dove",
        "Dove Men+Care", "Hellmann's", "Kissan", "Knorr", "Lifebuoy", "Lipton", "Liquid I.V.",
        "Lux", "Magnum", "Nutrafol", "OLLY", "OMO", "Onnit", "Paula's Choice", "Pepsodent",
        "Pond's", "Pureit", "Rexona", "Rin", "Seventh Generation", "Signal", "Simple",
        "SmartyPants", "Sunlight", "Sunsilk", "Surf Excel", "TRESemme", "The Vegetarian Butcher",
        "Vaseline",
        # Present in mv_campaign_day_features_v1 but were missing from this list:
        "Boost", "Bru", "Clinic Plus", "Close Up", "Domex", "Horlicks",
    ]

    BRAND_REGEX = build_brand_pattern(RAW_BRANDS)

    def regex_find_brands(user_query: str) -> List[str]:
        return list({m.group(0) for m in BRAND_REGEX.finditer(user_query)})
    
    matched_brands = regex_find_brands(user_query)
    brand_name = matched_brands[0] if matched_brands else tool_context.state.get("default_brand", "None")
    print(f"🧾 Extracted brand: {brand_name}")
    report_type_match = re.search(
        r"(?i)\b(Campaign Performance Report|Performance Report|Budget Report)\b",
        user_query,
    )

    # 🆕 Detect campaign ID if present (CMP_XXXX style)
    #campaign_id_match = re.search(r"(?i)\b(CMP[_\-]?\d{4,})\b", user_query)
    #campaign_id_match = re.search(r"(?i)(CMP[_\-]?\d{4,})", user_query)
    # Match campaign IDs with any short letter prefix (e.g. CMP_2025_0001, SYN_2025_0056), not just CMP_.
    campaign_id_match = re.search(r"(?i)\b([A-Za-z]{2,6}[_\-]\d{4}[_\-]\d+)\b", user_query)

    campaign_id = campaign_id_match.group(1).strip() if campaign_id_match else "None"

    # === Objective extraction ===
    OBJECTIVE_CHOICES = ["Conversion", "Consideration", "Awareness", "Retention"]
    OBJECTIVE_ALIASES = {"awareless": "Awareness", "retension": "Retention"}

    def _extract_objective(uq: str):
        uq_norm = _normalize_text(uq)
        # Direct match any choice
        for o in OBJECTIVE_CHOICES:
            if re.search(rf"\b{re.escape(_normalize_text(o))}\b", uq_norm):
                return o
        # aliases
        for alias, canonical in OBJECTIVE_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", uq_norm):
                return canonical
        # fuzzy match best effort
        best = None
        best_score = 0.0
        for o in OBJECTIVE_CHOICES:
            score = _ratio(_normalize_text(o), uq_norm)
            if score > best_score:
                best_score = score
                best = o
        return best if best_score >= 0.7 else None

    objective = _extract_objective(user_query)
    if objective:
        print(f"🎯 Extracted objective: {objective}")

    time_struct = extract_explicit_time_period(user_query)
    print(f"⏱️ Extracted time struct: {time_struct}")

    if time_struct is None:
        time_period = "Overall duration of campaign"
    else:
        time_period = f"{time_struct['start_date']} to {time_struct['end_date']}" if time_struct["type"] == "range" else time_struct["start_date"]

    report_type = report_type_match.group(1).strip().title() if report_type_match else tool_context.state.get(
        "default_report_type", "Campaign Performance Report"
    )

    """ Design Fallback case:"""

    if not brand_name or brand_name == "None":
        return {
            "status": "missing_information",
            "message": "Please provide a valid brand name to generate the report."
        }

    if not campaign_id or campaign_id == "None":
        return {
            "status": "missing_information",
            "message": "Please provide a valid campaign ID or campaign name."
        }

    if not objective:
        return {
            "status": "missing_information",
            "message": "Please specify the campaign objective (one of: Conversion, Consideration, Awareness, Retention)."
        }

    # # 🪄 Store extracted filters
    # tool_context.state.update({
    #     "persona_name": persona_name,
    #     "brand_name": brand_name,
    #     "time_period": time_period,
    #     "report_type": report_type,
    #     "campaign_id": campaign_id,
    # })

    filters = {
    "persona": persona_name,
    "brand": brand_name,
    "objective": objective,
    "duration": time_period,
    "report_type": report_type,
    "campaign_id": campaign_id
    }

    tool_context.state.update({
        "report_filters": filters,
        "objective": objective,
    })

    print(f"🧾 Filters: Persona={persona_name}, Brand={brand_name}, Objective={objective}, Period={time_period}")
    if campaign_id:
        print(f"🎯 Campaign ID detected: {campaign_id}")

    # 5️⃣ Persona context
    result = get_tone_and_kpis(
        persona_raw,
        role=persona_name,
        objective=objective
    )

    persona_tone = result.get("tone", "Professional, concise") if result else "Professional, concise"
    focus_kpis = result.get("relevant_kpis", ["ROAS", "CTR", "Conversions"]) if result else ["ROAS", "CTR", "Conversions"]

    # persona_data = persona_json.get(persona_name, {})
    # persona_tone = ", ".join(persona_data.get("tone", ["Professional", "concise"])) if isinstance(
    #     persona_data.get("tone"), list
    # ) else persona_data.get("tone", "Professional, concise")
    # persona_focus_kpis = persona_data.get("focus_kpis", ["ROAS", "CTR", "Conversions"])

    print(f"🧑 Persona: {persona_name}, Tone: {persona_tone}, Focus KPIs: {focus_kpis}")
    # 6️⃣ Persona report matrix
    report_obj = (
        persona_report_json.get(persona_name, {})
        .get("objectives", {})
        .get(report_type, {})
    )
    data_granularity = report_obj.get("data_granularity", "Daily")
    visualization_pref = report_obj.get("visualization_pref", ["Charts", "KPIs"])
    output_pref = report_obj.get("output_pref", ["Slide Deck + Report"])

    # 7️⃣ Load report schema
    schema_path = os.path.join(os.getcwd(), "data", "campaign_performance_report.json")
    if not os.path.exists(schema_path):
        schema_path = os.path.join(os.getcwd(), "Data", "campaign_performance_report.json")
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            report_schema = json.load(f)
        print(f"📂 Loaded report schema from: {schema_path}")
    except Exception as e:
        print(f"⚠️ Failed to load report schema: {e}")
        report_schema = {}
    tool_context.state["report_template"] = report_schema
    campaign_report = report_schema.get("Campaign_Performance_Report", {})
    report_sections = list(campaign_report.keys()) or [
        "1.Context",
        "3.Executive_Summary", 
        "4.Campaign_Overview",
        "5.Campaign_Wise_Analysis",
        "6.Recommendations",
    ]
    print(f"📂 Report sections defined: {report_sections}")

    # 8️⃣ Generate prompts safely with Gemini (final version with logging)
    prompt_list = []
    if use_gemini:
        print('use gemini')
        # 🧩 Include campaign ID in prompt only if available
        campaign_phrase = f" (Campaign ID: {campaign_id})" if campaign_id else ""
        fusion_prompt = f"""You are acting as a prompt generator agent to assist {persona_name} in preparing prompts which will be useful while generating {report_type} (responses of these prompts addresses different sections of {report_type} through which downstreamm agents will create the report) 
            report for brand name {brand_name} and Campaign Id {campaign_id} if mentioned (otherwise ask user to give specific brand and campaign id or name to move forward), covering the {time_period} if given (otherwise analyze for all the period for which data is available).

            Campaign: {campaign_id}
            Report Type: {report_type}
            Time Period: {time_period}

            Focus KPIs: {focus_kpis}
            Granularity: {data_granularity}
            Tone: {persona_tone}

            Goal:
            Generate a list of independent prompts that will help retrieve insights for the following sections:

            • Context
            • Campaign Overview
            • Campaign-wise Analysis

            Rules:

            1. Prompts must look like natural user questions.
            2. Do not generate SQL.
            3. Prompts must be independent.
            4. Do not generate a prompt that requests the full report at once.  do not even mention anywhere in the prompts that these are for purpose of generating report.
            5. If campaign_id and brand_name are available , include them clearly (a must step).
            6. Unknown values should be written generically  so they can be replaced later.
            7. Generate multiple prompts for each section.
        granularity
            Section requirements:

            Context
            Generate single prompts requesting campaign details including all below:
            Campaign ID, Unique Campaign Names, Brand Name,Unique Campaign Ad Id, Category, Media Types, Channel,
            Objective, Sub-Objective, Campaign Duration, Unique Planned Spend,Daily Total Actual Spend for {time_period}.

            Campaign Overview
            Generate multiple prompts requesting campaign overview tables including:
            Campaign ID, Campaign Name, Planned Spend, Campaign Objective,
            Total Ad Spend, Spend Utilization in one prompt.
            KPI tables based on {focus_kpis} in another 2 prompts as follows:
            1. We want range of values available( variation in values) for each KPIs.
            2. We want aggregated values ( *grouped by channel) of KPIs.
            -Should strictly not be any example from all values.
 
            Campaign-wise Analysis
            Generate prompts requesting visualization for each KPI in {focus_kpis[:3]} including:
            *trend analysis.

            Must include in this section's prompts:
            1. Campaign and brand: {campaign_id} and {brand_name}.
            2. Data granularity: {data_granularity} (Daily, Weekly)
            3. Campaign objective: {objective}
            4. Time Period: {time_period}
            5. Ask for plots of KPIs.

            Ask for visualizations of each KPIs in separate prompt.
            For example :
                if the focus KPIs are ROAS, CTR, and Conversions, the prompt for ROAS, CTR and Conversion sections should be separate . 

            Also generate single prompt asking for a concise campaign performance summary
            highlighting KPI performance, anomalies, and trends.


            DATA FILTERING
                Always filter by:
                • Campaign ID
                • Brand           

            Return JSON:

            {{
            "Context": [],
            "Campaign Overview": [],
            "Campaign-wise Analysis": []
            }}
            
            """

        try:
            # ✅ Always pass as list for Vertex AI

            model = GenerativeModel(model_name)
            gen_config=GenerationConfig(temperature=temperature,response_schema=TypeAdapter(List[PromptList]).json_schema(),response_mime_type='application/json')
            response = model.generate_content(
                fusion_prompt,
                generation_config=gen_config
            )



            # 🔍 Debug prints
            print("🔍 Raw Gemini response object:", response)
            print("🔍 Response.text:", getattr(response, "text", None))
            #print(response.content)
            

            # ✅ Extract text safely
            response_text = safe_extract_text(response)
            print("🧾 Extracted Text (first 300 chars):", response_text[:300], "...")

            tool_context.state["model_response"] = response_text

            # ✅ Try JSON parse (auto-remove Markdown wrappers)
            try:
                cleaned_text = response_text.strip()
                if cleaned_text.startswith("```"):
                    cleaned_text = re.sub(r"^```(?:json)?", "", cleaned_text)
                    cleaned_text = re.sub(r"```$", "", cleaned_text)
                cleaned_text = cleaned_text.strip()

                prompt_list = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                print(f"⚠️ Gemini returned non-JSON format ({e}). Using fallback prompt generation.")
                prompt_list = []

            # 🪵 Log full raw response for future debugging
            try:
                log_dir = tool_context.state.get("log_dir", "logs")
                os.makedirs(log_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")

                raw_log_path = os.path.join(log_dir, f"gemini_raw_response_{ts}.json")

                raw_data = {
                    "timestamp": ts,
                    "prompt_used": fusion_prompt.strip(),
                    "raw_response": getattr(response, "text", None) or str(response),
                }

                with open(raw_log_path, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, indent=2)

                print(f"🪵 Saved Gemini raw response log: {raw_log_path}")
            except Exception as log_err:
                print(f"⚠️ Failed to log raw Gemini response: {log_err}")

        except Exception as e:
            print(f"⚠️ Gemini call failed: {e}")
            use_gemini = False

    # 9️⃣ Fallback prompt generator
    if not use_gemini or not prompt_list:
        for section_name in report_sections:
            if "Executive" in section_name:
                prompt_list.append(
                    f"State key campaign objectives for {brand_name} in {time_period}. "
                    f"Summarize {data_granularity.lower()} ROAS, CTR, and Conversions."
                )
            elif "Overview" in section_name:
                prompt_list.append(
                    f"Provide performance overview across channels for {brand_name} in {time_period}. "
                    f"Include spend, ROAS, and CTR."
                )
            elif "Analysis" in section_name:
                prompt_list.append(
                    f"Analyze {data_granularity.lower()} trends for {brand_name} in {time_period}, "
                    f"focusing on ROAS, CTR, and Conversions."
                )
            elif "Recommendations" in section_name:
                prompt_list.append(
                    f"Suggest actionable optimizations for future campaigns of {brand_name} based on {time_period} insights."
                )
            elif "Context" in section_name:
                prompt_list.append(
                    f"List campaign IDs, objectives, duration, and spend details for {brand_name}'s {time_period} campaign."
                )
            else:
                prompt_list.append(
                    f"Summarize key insights for {section_name} of {brand_name}'s {time_period} performance report."
                )

    # 🔟 Save prompt list & user query with timestamp
    try:
        log_dir = tool_context.state.get("log_dir", "logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        prompt_json_path = os.path.join(log_dir, f"prompt_list_{timestamp}.json")
        with open(prompt_json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"timestamp": timestamp, "session_id": session_id, "prompt_list": prompt_list},
                f,
                indent=2,
            )

        user_query_log = os.path.join(log_dir, f"user_query_{timestamp}.txt")
        with open(user_query_log, "w", encoding="utf-8") as f:
            f.write(
                f"Timestamp: {timestamp}\nSession ID: {session_id}\nUser Query: {user_query}\n"
            )

        print(f"🪵 Saved prompt list: {prompt_json_path}")
        print(f"🪵 Saved user query: {user_query_log}")

    except Exception as e:
        print(f"⚠️ Failed to save logs: {e}")

    # ✅ Return compact payload
    tool_context.state["prompt_generated"] = {
        "status": "success",
        "persona": persona_name,
        "prompt_list": prompt_list,
        "filters": {
            "brand": brand_name,
            "duration": time_period,
            "report_type": report_type,
            "campaign_id": campaign_id,
        },
        "timestamp": datetime.now().isoformat(),
    }
    tool_context.state["prompt_generator_out"] = prompt_list

    print(f"🟢 Generated {len(prompt_list)} prompts successfully at {time.strftime('%H:%M:%S')}.")
    return prompt_list

# Follow the structure mentioned in below example -Prompt for generating content for each section should be in below format and should be in list format as shown below:
    # "prompt_list": [
    #     {{
    #     "section_name": "Context",
    #     "prompts": [
    #         "Prompts for Context..."
    #     ]
    #     }},
    #     {{
    #     "section_name": "Customization Options",
    #     "prompts": [
    #         "Prompts for Customization Options..."
    #     ]
    #     }},
    #     {{
    #     "section_name": "Campaign Overview",
    #     "prompts": [
    #         "Prompts for Campaign Overview...",
    #         "Prompts for Campaign Overview...",
    #     ]
    #     }},
    #     {{
    #     "section_name": "Campaign-wise Analysis",
    #     "prompts": [
    #         "Prompts for Campaign-wise Analysis - ROAS...",
    #         "Prompts for Campaign-wise Analysis - CTR...",
    #         "Prompts for Campaign-wise Analysis - Conversions...",      
    #     ]
    #     }}
    # ]



# import re
# import os
# import json
# from datetime import datetime
# from google.adk.tools import ToolContext
# from vertexai.preview.generative_models import GenerativeModel


# # ✅ Helper to safely parse bools
# def _parse_bool(v, default=True):
#     if isinstance(v, bool):
#         return v
#     if isinstance(v, (int, float)):
#         return bool(v)
#     if isinstance(v, str):
#         s = v.strip().lower()
#         if s in {"true", "1", "yes", "y"}:
#             return True
#         if s in {"false", "0", "no", "n"}:
#             return False
#     return default

# # ✅ Helper to safely extract text from Gemini response
# def safe_extract_text(response):
#     try:
#         if hasattr(response, "text"):
#             return response.text.strip()
#         if hasattr(response, "candidates") and response.candidates:
#             return response.candidates[0].content.parts[0].text.strip()
#         return str(response).strip()
#     except Exception:
#         return ""
    
# import re
# from difflib import SequenceMatcher
# from typing import Dict, List, Tuple

# def _normalize_text(s: str) -> str:
#     """
#     Lowercase, decode common HTML entities (&amp; → &), collapse punctuation and spaces.
#     Also normalizes underscores/hyphens to spaces and trims.
#     """
#     if s is None:
#         return ""
#     s = s.replace("&amp;", "&")
#     s = s.lower()
#     # replace underscores/hyphens/slashes with spaces
#     s = re.sub(r"[_/\-]+", " ", s)
#     # keep alphanumerics and & only; convert the rest to spaces
#     s = re.sub(r"[^a-z0-9&\s]", " ", s)
#     s = re.sub(r"\s+", " ", s).strip()
#     return s

# def _tokenize(s: str) -> List[str]:
#     return [t for t in _normalize_text(s).split() if t]

# def _ratio(a: str, b: str) -> float:
#     """Fallback similarity. If you have rapidfuzz, swap in token_set_ratio or partial_ratio."""
#     return SequenceMatcher(None, a, b).ratio()

# def _acronym(name: str) -> str:
#     """
#     Build a naive acronym: first letters of tokens ignoring short/common words.
#     Example: 'Client Solution Manager' -> 'csm'
#     """
#     toks = _tokenize(name)
#     toks = [t for t in toks if t not in {"and", "&", "of", "the"}]
#     return "".join(t[0] for t in toks) if toks else ""

# def resolve_persona(
#     user_query: str,
#     available_personas: List[str],
#     persona_alias_map: Dict[str, List[str]] = None,
#     min_conf_exact: float = 0.92,   # high threshold for near-exact
#     min_conf_good: float = 0.80,    # good fuzzy match
#     min_conf_ok: float = 0.68       # acceptable with token overlap / partial
# ) -> Dict[str, str]:
#     """
#     Returns: {"persona_name": <best match or None>, "score": <0..1>, "matched_alias": <alias or None>, "evidence": <why>}
#     - Uses normalization, alias/acro matching, token overlap, containment, and fuzzy similarity.
#     - Prefers exact/alias/acro matches; falls back to fuzzy.
#     """
#     uq_norm = _normalize_text(user_query)
#     uq_tokens = set(_tokenize(user_query))

#     # Build candidate rows: for each persona, include base name, aliases, acronym
#     rows: List[Tuple[str, str, str]] = []  # (canonical_persona, candidate_variant, variant_type)
#     for p in available_personas:
#         # Decode HTML entities and normalize display name now
#         p_disp = p.replace("&amp;", "&")
#         variants = [p_disp]
#         vtypes  = ["name"]

#         # aliases
#         if persona_alias_map and p in persona_alias_map:
#             aliases = persona_alias_map[p] or []
#             aliases = [a.replace("&amp;", "&") for a in aliases]
#             variants.extend(aliases)
#             vtypes.extend(["alias"] * len(aliases))

#         # acronym
#         acro = _acronym(p_disp)
#         if acro:
#             variants.append(acro)
#             vtypes.append("acronym")

#         for v, t in zip(variants, vtypes):
#             rows.append((p_disp, v, t))

#     # Score each candidate variant
#     best = {"persona_name": None, "score": 0.0, "matched_alias": None, "evidence": ""}
#     for canonical, variant, vtype in rows:
#         v_norm = _normalize_text(variant)
#         v_tokens = set(_tokenize(variant))

#         score = 0.0
#         evidence = []

#         # 1) Exact normalized equality
#         if v_norm and (v_norm == uq_norm):
#             score = 1.0
#             evidence.append("exact")
#         # 2) Substring containment (user mentions the variant)
#         elif v_norm and v_norm in uq_norm:
#             score = 0.93
#             evidence.append("substring")
#         # 3) Token overlap Jaccard-ish
#         elif v_tokens:
#             inter = len(uq_tokens & v_tokens)
#             union = len(uq_tokens | v_tokens)
#             jacc = inter / union if union else 0.0
#             # weight token overlap; scale a bit
#             score = max(score, 0.70 + 0.20 * jacc) if inter else score
#             if inter:
#                 evidence.append(f"token_overlap:{inter}/{union}")
#         # 4) Fuzzy similarity as fallback
#         sim = _ratio(v_norm, uq_norm) if v_norm else 0.0
#         # combine (keep the strongest)
#         score = max(score, sim)

#         # Keep best by score; break ties preferring canonical name over alias/acronym
#         if (score > best["score"]) or (abs(score - best["score"]) < 1e-6 and best["persona_name"] is None and vtype == "name"):
#             best = {
#                 "persona_name": canonical,
#                 "score": float(score),
#                 "matched_alias": variant if vtype != "name" else None,
#                 "evidence": ",".join(evidence) if evidence else ("fuzzy" if sim == score else "")
#             }

#     # Apply confidence thresholds
#     # Promote only if acceptable; otherwise return None to trigger disambiguation upstream.
#     if best["score"] >= min_conf_exact:
#         best["evidence"] = best["evidence"] or "near_exact"
#         return best
#     if best["score"] >= min_conf_good:
#         best["evidence"] = best["evidence"] or "good_fuzzy"
#         return best
#     if best["score"] >= min_conf_ok:
#         best["evidence"] = best["evidence"] or "ok_fuzzy"
#         return best

#     # Not confident — return None and score for upstream handling (e.g., propose top options)
#     return {"persona_name": None, "score": float(best["score"]), "matched_alias": None, "evidence": "low_confidence"}

# import re
# import html

# def build_brand_pattern(brands: List[str]) -> re.Pattern:
#     """
#     Build a regex that tolerates punctuation and '&'/'and' variation.
#     We escape brand tokens and allow flexible separators between words.
#     """
#     def brand_to_pattern(b: str) -> str:
#         b = html.unescape(b)
#         # split into tokens; convert '&' to pattern (?:&|and)
#         tokens = re.split(r"\s+", b.strip())
#         patt_tokens = []
#         for t in tokens:
#             if t.lower() in {"&", "and"} or t == "&":
#                 patt_tokens.append(r"(?:&|and)")
#             else:
#                 # allow internal punctuation variations
#                 t_escaped = re.escape(t).replace(r"\+", r"\+")
#                 # accept optional punctuation/spaces between letters (e.g., I.V. vs IV)
#                 t_escaped = re.sub(r"\\\.", r"[\.]?", t_escaped)
#                 patt_tokens.append(t_escaped)
#         # allow flexible separators between tokens
#         return r"\b" + r"\s*[-\s]*\s*".join(patt_tokens) + r"\b"

#     alternates = [brand_to_pattern(b) for b in brands]
#     full = "(?i)(" + "|".join(alternates) + ")"
#     return re.compile(full)

# import re
# from datetime import datetime

# def extract_explicit_time_period(user_query: str):
#     result = {
#         "start_date": "",
#         "end_date": "",
#         "type": ""
#     }

#     month_map = {
#         "jan": 1, "feb": 2, "mar": 3, "apr": 4,
#         "may": 5, "jun": 6, "jul": 7, "aug": 8,
#         "sep": 9, "oct": 10, "nov": 11, "dec": 12
#     }

#     pattern = re.search(
#         r"(?i)time_period\s*:\s*(\d{1,2})\s+"
#         r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
#         r"(\d{4})\s*[-–]\s*"
#         r"(\d{1,2})\s+"
#         r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
#         r"(\d{4})",
#         user_query
#     )

#     if not pattern:
#         return result

#     d1, m1, y1, d2, m2, y2 = pattern.groups()

#     start = datetime(int(y1), month_map[m1[:3].lower()], int(d1))
#     end = datetime(int(y2), month_map[m2[:3].lower()], int(d2))

#     result["start_date"] = start.strftime("%Y-%m-%d")
#     result["end_date"] = end.strftime("%Y-%m-%d")
#     result["type"] = "range"

#     return result

# async def generate_prompt(tool_context: ToolContext, **kwargs):
#     """Generate structured Instruction + List of Prompts safely for Campaign Performance Report."""

#     print(" Inside Prompt Generator Agent")
#     session_id = getattr(tool_context._invocation_context.session, "id", "unknown_session")
#     print(f"Session ID: {session_id}")

#     # --- CONFIG ---
#     use_gemini = _parse_bool(tool_context.state.get("use_gemini", True))
#     temperature = float(tool_context.state.get("temperature", 0.02))
#     model_name = (
#         tool_context.state.get("generator_model")
#         or os.getenv("SEQUENTIAL_AGENT")
#         or "gemini-1.5-pro"
#     )
#     tool_context.state["modelused"] = model_name

#     # 1️⃣ Extract user query
#     user_query = str(tool_context.state.get("user_query", "")).strip()
#     print(f"🧠 User Query: {user_query}")

#     # 2️⃣ Load persona & persona_report safely (accepts dict OR list)
#     persona_raw = tool_context.state.get("persona", "{}")
#     persona_report_raw = tool_context.state.get("persona_report", "{}")
#     # print(f"📂 Loaded persona (raw): {str(persona_raw)[:200]}...")
#     # print(f"📂 Loaded persona_report (raw): {str(persona_report_raw)[:200]}...")

#     def ensure_dict(obj):
#         """Safely convert list/string to dict."""
#         if isinstance(obj, dict):
#             return obj
#         if isinstance(obj, list):
#             try:
#                 return {item.get("persona") or item.get("name") or "Unknown": item for item in obj}
#             except Exception:
#                 return {}
#         if isinstance(obj, str):
#             try:
#                 parsed = json.loads(obj)
#                 return ensure_dict(parsed)
#             except Exception:
#                 return {}
#         return {}

#     persona_json = ensure_dict(persona_raw)
#     persona_report_json = ensure_dict(persona_report_raw)

#     # 3️⃣ Extract attributes (regex hardened to avoid N/A)
#     available_personas = tool_context.state.get(
#         "available_personas",
#         ["Client Solution Manager", "Ad Ops Analyst","Ad Ops Manager","AI Engineer (Sell)", "Retail Media Owner", "Media & Campaign Manager_New","Brand Manager new","AI Engineer (Buy)"],
#     )
    
#     persona_alias_map = {
#         "Client Solution Manager": ["Client Solutions Manager", "CSM", "Solutions Manager"],
#         "Ad Ops Analyst": ["Ad Operations Analyst", "Advertising Ops Analyst"],
#         "Ad Ops Manager": ["Ad Operations Manager", "AdOps Manager"],
#         "AI Engineer (Sell)": ["AI Engineer Sell", "AI Sell Engineer"],
#         "AI Engineer (Buy)": ["AI Engineer Buy", "AI Buy Engineer"],
#         "Retail Media Owner": ["RMO", "Retail Media Lead", "Retail Media"],
#         "Media & Campaign Manager_New": ["Media and Campaign Manager", "Media & Campaign Manager", "Campaign Manager"],
#         "Brand Manager new": ["Brand Manager", "BM"],
#     }

#     persona_res = resolve_persona(user_query, available_personas, persona_alias_map)

#     if persona_res["persona_name"]:
#         persona_name = persona_res["persona_name"]
#     else:
#         # keep your default, but also surface top suggestions upstream (optional: compute top 3 by score)
#         persona_name = tool_context.state.get("default_persona", "Media & Campaign Manager_New")

#     # brand_match = re.search(r"(?i)\bfor\s+([A-Za-z0-9&\-\s]+?)\s+(?:brand|product)\b", user_query)

#     """ Get brand names mentioned in the user query using regex pattern matching. The pattern is built to be flexible with punctuation and conjunctions. 
#     """

#     RAW_BRANDS = [
#         "Axe", "Baby Dove", "Ben & Jerry's", "Brooke Bond", "Cif", "Clear", "Comfort",
#         "Continental", "Cornetto", "Dermalogica", "Dollar Shave Club", "Domestos", "Dove",
#         "Dove Men+Care", "Hellmann's", "Kissan", "Knorr", "Lifebuoy", "Lipton", "Liquid I.V.",
#         "Lux", "Magnum", "Nutrafol", "OLLY", "OMO", "Onnit", "Paula's Choice", "Pepsodent",
#         "Pond's", "Pureit", "Rexona", "Rin", "Seventh Generation", "Signal", "Simple",
#         "SmartyPants", "Sunlight", "Sunsilk", "Surf Excel", "TRESemme", "The Vegetarian Butcher",
#         "Vaseline"
#     ]

#     BRAND_REGEX = build_brand_pattern(RAW_BRANDS)

#     def regex_find_brands(user_query: str) -> List[str]:
#         return list({m.group(0) for m in BRAND_REGEX.finditer(user_query)})
    
#     matched_brands = regex_find_brands(user_query)
#     brand_name = matched_brands[0] if matched_brands else tool_context.state.get("default_brand", "None")

#     report_type_match = re.search(
#         r"(?i)\b(Campaign Performance Report|Performance Report|Budget Report)\b",
#         user_query,
#     )

#     # 🆕 Detect campaign ID if present (CMP_XXXX style)
#     #campaign_id_match = re.search(r"(?i)\b(CMP[_\-]?\d{4,})\b", user_query)
#     #campaign_id_match = re.search(r"(?i)(CMP[_\-]?\d{4,})", user_query)
#     campaign_id_match = re.search(r"(?i)(CMP[_\-0-9]+)", user_query)

#     campaign_id = campaign_id_match.group(1).strip() if campaign_id_match else "None"

#     time_struct = extract_explicit_time_period(user_query)
#     print(f"⏱️ Extracted time struct: {time_struct}")

#     if time_struct is None:
#         time_period = "Overall duration of campaign"
#     else:
#         time_period = f"{time_struct['start_date']} to {time_struct['end_date']}" if time_struct["type"] == "range" else time_struct["start_date"]

#     report_type = report_type_match.group(1).strip().title() if report_type_match else tool_context.state.get(
#         "default_report_type", "Campaign Performance Report"
#     )

#     """ Design Fallback case:"""

#     if not brand_name or brand_name == "None":
#         return {
#             "status": "missing_information",
#             "message": "Please provide a valid brand name to generate the report."
#         }

#     if not campaign_id or campaign_id == "None":
#         return {
#             "status": "missing_information",
#             "message": "Please provide a valid campaign ID or campaign name."
#         }

#     # 🪄 Store extracted filters
#     tool_context.state.update({
#         "persona_name": persona_name,
#         "brand_name": brand_name,
#         "time_period": time_period,
#         "report_type": report_type,
#         "campaign_id": campaign_id,
#     })

#     print(f"🧾 Filters: Persona={persona_name}, Brand={brand_name}, Period={time_period}")
#     if campaign_id:
#         print(f"🎯 Campaign ID detected: {campaign_id}")

#     # 5️⃣ Persona context
#     persona_data = persona_json.get(persona_name, {})
#     persona_tone = ", ".join(persona_data.get("tone", ["Professional", "concise"])) if isinstance(
#         persona_data.get("tone"), list
#     ) else persona_data.get("tone", "Professional, concise")
#     persona_focus_kpis = persona_data.get("focus_kpis", ["ROAS", "CTR", "Conversions"])

#     # 6️⃣ Persona report matrix
#     report_obj = (
#         persona_report_json.get(persona_name, {})
#         .get("objectives", {})
#         .get(report_type, {})
#     )
#     data_granularity = report_obj.get("data_granularity", "Monthly")
#     visualization_pref = report_obj.get("visualization_pref", ["Charts", "KPIs"])
#     output_pref = report_obj.get("output_pref", ["Slide Deck + Report"])

#     # 7️⃣ Load report schema
#     schema_path = os.path.join(os.getcwd(), "data", "campaign_performance_report.json")
#     if not os.path.exists(schema_path):
#         schema_path = os.path.join(os.getcwd(), "Data", "campaign_performance_report.json")
#     try:
#         with open(schema_path, "r", encoding="utf-8") as f:
#             report_schema = json.load(f)
#         print(f"📂 Loaded report schema from: {schema_path}")
#     except Exception as e:
#         print(f"⚠️ Failed to load report schema: {e}")
#         report_schema = {}
#     tool_context.state["report_template"] = report_schema
#     campaign_report = report_schema.get("Campaign_Performance_Report", {})
#     report_sections = list(campaign_report.keys()) or [
#         "1.Context",
#         "2.Customization_Options",
#         "3.Executive_Summary",
#         "4.Campaign_Overview",
#         "5.Campaign_Wise_Analysis",
#         "6.Recommendations",
#     ]
#     print(f"📂 Report sections defined: {report_sections}")

#     # 8️⃣ Generate prompts safely with Gemini (final version with logging)
#     prompt_list = []
#     if use_gemini:
#         # 🧩 Include campaign ID in prompt only if available
#         campaign_phrase = f" (Campaign ID: {campaign_id})" if campaign_id else ""
#         fusion_prompt = f"""
# You are acting as a prompt generator agent to assist {persona_name} in preparing prompts which will be useful while generating {report_type} (responses of these prompts addresses different sections of {report_type} through which downstreamm agents will create the report) report for brand name {brand_name}and Campaign Id {campaign_phrase} if mentioned (otherwise ask user to give specific brand and campaign id or name to move forward), covering the {time_period} if given (otherwise analyze for all the period for which data is available).
# Generate a natural list of user prompts (not SQL) to help fill out the sections of the report mentioned below:
# Context, Customization Options, Campaign Overview, Campaign-wise Analysis.
# Below are the examples for some sections that you can use as a reference to generate the prompts for each section:
# 1. Context:
#     Campaign 1
#     Campaign ID: CMP_2025_0001
#     Campaign Name: Dove Nourishing Body Wash Launch
#     Brand Name: Dove
#     Category: Personal Care
#     Media Type(s): Video, Shoppable Display, Social Ads
#     Channel(s): Onsite, Offsite
#     Objective: Conversion
#     Sub-Objective: Drive Sales / Purchases, Add to Cart, Basket Building, Retarget PDP Viewers, Buy
#     Box Wins
#     Campaign Manager: Jane Smith
#     Campaign Duration: 2025-05-01 – 2025-06-30
#     Planned Budget: $50,000
#     Actual Spend: $45,000 (till date)
#     Campaign 2
#     Campaign ID: CMP_2025_0002
#     Campaign Name: Dove Deodorant Awareness
#     Brand Name: Dove
#     Category: Personal Care
#     Media Type(s): Video, CTV
#     Channel(s): Channel-CTV
#     Objective: Awareness
#     Sub-Objective: Brand Awareness, Brand Recall, Video Views, Product Launch, Reach New
#     Households, Category Awareness
#     Campaign Manager: John Doe
#     Campaign Duration: 2025-05-01 – 2025-06-30
#     Planned Budget: $30,000
#     Actual Spend: $28,000 (till date)

# 2. Customization option: 
#     This report can be filtered and customized along the following dimensions:
#         • Timeline: Daily report view
#         • By Creative: Segmented by channel (App, Channel-CTV, Onsite, Offsite, Instore

# 4. Campaign Overview:
#     The prompt created for this section should be some thing similar to this-

#     "This section provides an overview of the campaign, but the information can be summarized more clearly and efficiently using tables. Please try to generate prompts asking to include well‑structured tables for campaign overview.
#     Start with a high‑level campaign summary table that includes (but is not limited to) the following columns:

#     Campaign ID
#     Campaign Name
#     Budget (Planned Spend)
#     Campaign Objective (Awareness, Consideration, Conversion, Retention)
#     Total Ad Spend
#     Budget Utilization

#     After creating the summary table, generate objective-specific tables.
#     For example, if the selected Campaign Objective is Awareness, create an ‘Awareness Campaign Performance’ table with columns such as:

#     Channel
#     Total Ad Spend
#     Impressions
#     Unique Reach
#     Frequency
#     ROAS
#     CPM

#     Ensure the tables are clean, easy to understand, and formatted to provide a clear performance overview. Use consistent column naming conventions, align numeric values properly, and structure the tables to enable quick comparisons across campaigns and channels."

#     ** Important **
#     1. Split the prompts for this section so that different tables or sets of questions are generated through different prompts, for step by step functioning of LLM model and not complex fetching task at same time.
#     2. Ensure that the prompts for this section are independent of each other, so that all dimensions of campaign overview are covered by different prompts and the LLM can focus on one aspect at a time while generating the report.

# 5. Campaign-wise Analysis:
#     This section provides a detailed analysis of campaign performance.
#     This section requires some basic details of the campaign such as campaign name or campaign ad id or campaign duration etc mentioned in the user query or already fetched in previous cycle , so that the insights generated are specific to that campaign.
#     The analysis should be for the specific Campaign {campaign_id} and Brand {brand_name}, focused on analysis using {persona_focus_kpis} , {data_granularity} and Campaign Objective (*Do not use any objective, use objective of the asked campaign only). Generate separate prompt for fetching proper insight through plots and graphs for each {persona_focus_kpis}. 
#     For example, if the focus KPIs are ROAS, CTR, and Conversions, the prompt for ROAS, CTR and Conversion sections should be separate and should also support creating visualizations like charts or graphs to illustrate performance trends over time, across channels, or by audience segments. 
#     The analysis should also consider the data granularity (e.g., daily, weekly, monthly) to provide insights at the appropriate level of detail.
#     Points to be taken care while creating prompts for this section-
#     ** Important ** 
#     1. Make more than one prompts to support this section.
#     2. The prompts should cover different aspects and should be as independent as possible to cover the section comprehensively.

# **Very Important**
# Keep the prompts created for one section as sublist under the section name, so that it is clear that these prompts are for generating content for this section.
# Keep the model output format as :
#     class Section(BaseModel):
#         section_name: str
#         prompts: List[str]

#     class PromptListOutput(BaseModel):
#         prompt_list: List[Section]

# Tone: {persona_tone}.
# Focus KPIs: {', '.join(persona_focus_kpis)}.
# Data granularity: {data_granularity}.
# Return only a JSON array of prompt strings.

# ** Important**: 
# 1. If *campaign_id and *brand name is provided, include it in the prompts clearly(like for campaign id {campaign_id} and Brand name {brand_name}) to ensure insights are demanded specific to that campaign and brand. 
# 2. Do not try to generate a prompt for generating all report at once, instead generate specific prompts for {','.join(report_sections)} to ensure depth and relevance of insights.
# 3. Also, do not mention anywhere in the prompts that these are for purpose of generating report, instead make it look like a natural user query that a person would ask to get the insights related to campaign performance.
# 4. Try to make sections as independent (except for executive summary or other summary and campaign comparison.) possible, so that the report covers most aspects of the campaign performance comprehensively.
# """
#         try:
#             # ✅ Always pass as list for Vertex AI
#             model = GenerativeModel(model_name)
#             response = model.generate_content(
#                 [fusion_prompt],
#                 generation_config={"temperature": temperature}
#             )

#             # 🔍 Debug prints
#             print("🔍 Raw Gemini response object:", response)
#             print("🔍 Response.text:", getattr(response, "text", None))

#             # ✅ Extract text safely
#             response_text = safe_extract_text(response)
#             print("🧾 Extracted Text (first 300 chars):", response_text[:300], "...")

#             tool_context.state["model_response"] = response_text

#             # ✅ Try JSON parse (auto-remove Markdown wrappers)
#             try:
#                 cleaned_text = response_text.strip()
#                 if cleaned_text.startswith("```"):
#                     cleaned_text = re.sub(r"^```(?:json)?", "", cleaned_text)
#                     cleaned_text = re.sub(r"```$", "", cleaned_text)
#                 cleaned_text = cleaned_text.strip()

#                 prompt_list = json.loads(cleaned_text)
#             except json.JSONDecodeError as e:
#                 print(f"⚠️ Gemini returned non-JSON format ({e}). Using fallback prompt generation.")
#                 prompt_list = []

#             # 🪵 Log full raw response for future debugging
#             try:
#                 log_dir = tool_context.state.get("log_dir", "logs")
#                 os.makedirs(log_dir, exist_ok=True)
#                 ts = datetime.now().strftime("%Y%m%d_%H%M%S")

#                 raw_log_path = os.path.join(log_dir, f"gemini_raw_response_{ts}.json")

#                 raw_data = {
#                     "timestamp": ts,
#                     "prompt_used": fusion_prompt.strip(),
#                     "raw_response": getattr(response, "text", None) or str(response),
#                 }

#                 with open(raw_log_path, "w", encoding="utf-8") as f:
#                     json.dump(raw_data, f, indent=2)

#                 print(f"🪵 Saved Gemini raw response log: {raw_log_path}")
#             except Exception as log_err:
#                 print(f"⚠️ Failed to log raw Gemini response: {log_err}")

#         except Exception as e:
#             print(f"⚠️ Gemini call failed: {e}")
#             use_gemini = False

#     # 9️⃣ Fallback prompt generator
#     if not use_gemini or not prompt_list:
#         for section_name in report_sections:
#             if "Executive" in section_name:
#                 prompt_list.append(
#                     f"State key campaign objectives for {brand_name} in {time_period}. "
#                     f"Summarize {data_granularity.lower()} ROAS, CTR, and Conversions."
#                 )
#             elif "Overview" in section_name:
#                 prompt_list.append(
#                     f"Provide performance overview across channels for {brand_name} in {time_period}. "
#                     f"Include spend, ROAS, and CTR."
#                 )
#             elif "Analysis" in section_name:
#                 prompt_list.append(
#                     f"Analyze {data_granularity.lower()} trends for {brand_name} in {time_period}, "
#                     f"focusing on ROAS, CTR, and Conversions."
#                 )
#             elif "Recommendations" in section_name:
#                 prompt_list.append(
#                     f"Suggest actionable optimizations for future campaigns of {brand_name} based on {time_period} insights."
#                 )
#             elif "Context" in section_name:
#                 prompt_list.append(
#                     f"List campaign IDs, objectives, duration, and spend details for {brand_name}'s {time_period} campaign."
#                 )
#             else:
#                 prompt_list.append(
#                     f"Summarize key insights for {section_name} of {brand_name}'s {time_period} performance report."
#                 )

#     # 🔟 Save prompt list & user query with timestamp
#     try:
#         log_dir = tool_context.state.get("log_dir", "logs")
#         os.makedirs(log_dir, exist_ok=True)
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

#         prompt_json_path = os.path.join(log_dir, f"prompt_list_{timestamp}.json")
#         with open(prompt_json_path, "w", encoding="utf-8") as f:
#             json.dump(
#                 {"timestamp": timestamp, "session_id": session_id, "prompt_list": prompt_list},
#                 f,
#                 indent=2,
#             )

#         user_query_log = os.path.join(log_dir, f"user_query_{timestamp}.txt")
#         with open(user_query_log, "w", encoding="utf-8") as f:
#             f.write(
#                 f"Timestamp: {timestamp}\nSession ID: {session_id}\nUser Query: {user_query}\n"
#             )

#         print(f"🪵 Saved prompt list: {prompt_json_path}")
#         print(f"🪵 Saved user query: {user_query_log}")

#     except Exception as e:
#         print(f"⚠️ Failed to save logs: {e}")

#     # ✅ Return compact payload
#     tool_context.state["prompt_generated"] = {
#         "status": "success",
#         "persona": persona_name,
#         "prompt_list": prompt_list,
#         "filters": {
#             "brand": brand_name,
#             "duration": time_period,
#             "report_type": report_type,
#             "campaign_id": campaign_id,
#         },
#         "timestamp": datetime.now().isoformat(),
#     }
#     tool_context.state["prompt_generator_out"] = prompt_list

#     print(f"🟢 Generated {len(prompt_list)} prompts successfully.")
#     return prompt_list

# # Follow the structure mentioned in below example -Prompt for generating content for each section should be in below format and should be in list format as shown below:
#     # "prompt_list": [
#     #     {{
#     #     "section_name": "Context",
#     #     "prompts": [
#     #         "Prompts for Context..."
#     #     ]
#     #     }},
#     #     {{
#     #     "section_name": "Customization Options",
#     #     "prompts": [
#     #         "Prompts for Customization Options..."
#     #     ]
#     #     }},
#     #     {{
#     #     "section_name": "Campaign Overview",
#     #     "prompts": [
#     #         "Prompts for Campaign Overview...",
#     #         "Prompts for Campaign Overview...",
#     #     ]
#     #     }},
#     #     {{
#     #     "section_name": "Campaign-wise Analysis",
#     #     "prompts": [
#     #         "Prompts for Campaign-wise Analysis - ROAS...",
#     #         "Prompts for Campaign-wise Analysis - CTR...",
#     #         "Prompts for Campaign-wise Analysis - Conversions...",      
#     #     ]
#     #     }}
#     # ]
