import re
import os
import json
from datetime import datetime
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel


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


async def generate_prompt(tool_context: ToolContext, **kwargs):
    """Generate structured Instruction + List of Prompts safely for Campaign Performance Report."""

    print("🧩 Inside Prompt Generator Agent")
    session_id = getattr(tool_context._invocation_context.session, "id", "unknown_session")
    print(f"Session ID: {session_id}")

    # --- CONFIG ---
    use_gemini = _parse_bool(tool_context.state.get("use_gemini", True))
    temperature = float(tool_context.state.get("temperature", 0.2))
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
        ["Client Solution Manager", "Ad Ops Analyst", "Marketing Strategist", "Data Scientist"],
    )
    persona_pattern = "|".join(map(re.escape, available_personas))
    persona_match = re.search(fr"(?i)\b({persona_pattern})\b", user_query)
    brand_match = re.search(r"(?i)\bfor\s+([A-Za-z0-9&\-\s]+?)\s+(?:brand|product)\b", user_query)
    platform_match = re.search(r"(?i)\bon\s+([A-Za-z0-9&\-\s]+?)(?:,|\scovering\b|$)", user_query)
    time_match = re.search(
        r"(?i)\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
        r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
        user_query,
    )
    report_type_match = re.search(
        r"(?i)\b(Campaign Performance Report|Performance Report|Budget Report)\b",
        user_query,
    )

    # 4️⃣ Fallback defaults
    persona_name = persona_match.group(1).strip() if persona_match else tool_context.state.get("default_persona", "Client Solution Manager")
    brand_name = brand_match.group(1).strip() if brand_match else tool_context.state.get("default_brand", "Unknown Brand")
    platform = platform_match.group(1).strip() if platform_match else tool_context.state.get("default_platform", "Manager")
    time_period = time_match.group(0).strip() if time_match else tool_context.state.get("default_time_period", "Current Period")
    report_type = report_type_match.group(1).strip().title() if report_type_match else tool_context.state.get("default_report_type", "Campaign Performance Report")

    # 🪄 Store extracted filters
    tool_context.state.update({
        "persona_name": persona_name,
        "brand_name": brand_name,
        "platform": platform,
        "time_period": time_period,
        "report_type": report_type,
    })
    print(f"🧾 Filters: Persona={persona_name}, Brand={brand_name}, Platform={platform}, Period={time_period}")

    # 5️⃣ Persona context
    persona_data = persona_json.get(persona_name, {})
    persona_tone = ", ".join(persona_data.get("tone", ["Professional", "concise"])) if isinstance(persona_data.get("tone"), list) else persona_data.get("tone", "Professional, concise")
    persona_focus_kpis = persona_data.get("focus_kpis", ["ROAS", "CTR", "Conversions"])

    # 6️⃣ Persona report matrix
    report_obj = (
        persona_report_json.get(persona_name, {})
        .get("objectives", {})
        .get(report_type, {})
    )
    data_granularity = report_obj.get("data_granularity", "Monthly")
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
    tool_context.state['report_template'] = report_schema
    campaign_report = report_schema.get("Campaign_Performance_Report", {})
    report_sections = list(campaign_report.keys()) or [
        "1.Context",
        "2.Customization_Options",
        "3.Executive_Summary",
        "4.Campaign_Overview",
        "5.Campaign_Wise_Analysis",
        "6.Recommendations",
    ]

#     # 8️⃣ Generate prompts safely with Gemini
#     prompt_list = []
#     if use_gemini:
#         fusion_prompt = f"""
# You are acting as a {persona_name} preparing a {report_type} for {brand_name} on {platform}, covering {time_period}.
# Generate a natural list of user prompts (not SQL) to help fill each section of the report:
# {', '.join(report_sections)}.

# Tone: {persona_tone}.
# Focus KPIs: {', '.join(persona_focus_kpis)}.
# Data granularity: {data_granularity}.
# Return only a JSON array of prompt strings.
# """
#         try:
#             model = GenerativeModel(model_name)
#             #response = model.generate_content(fusion_prompt, generation_config={"temperature": temperature})
#             response = model.generate_content([fusion_prompt], generation_config={"temperature": temperature})
#             print("🔍 Full Gemini response:", response)
#             print("🔍 Extracted text:", safe_extract_text(response))


#             response_text = safe_extract_text(response)
#             tool_context.state["model_response"] = response_text

#             try:
#                 prompt_list = json.loads(response_text.strip())
#             except json.JSONDecodeError:
#                 print("⚠️ Gemini returned non-JSON. Falling back.")
#                 prompt_list = []

#         except Exception as e:
#             print(f"⚠️ Gemini failed: {e}. Using fallback.")
#             use_gemini = False

    # 8️⃣ Generate prompts safely with Gemini (final version with logging)
prompt_list = []
if use_gemini:

    fusion_prompt = f"""
You are acting as a {persona_name} preparing a {report_type} for {brand_name} on {platform}, covering {time_period}.
Generate a natural list of user prompts (not SQL) to help fill each section of the report:
{', '.join(report_sections)}.

Tone: {persona_tone}.
Focus KPIs: {', '.join(persona_focus_kpis)}.
Data granularity: {data_granularity}.
Return only a JSON array of prompt strings.
"""
    try:
        # ✅ Always pass as list for Vertex AI
        model = GenerativeModel(model_name)
        response = model.generate_content(
            [fusion_prompt],
            generation_config={"temperature": temperature}
        )

        # 🔍 Debug prints
        print("🔍 Raw Gemini response object:", response)
        print("🔍 Response.text:", getattr(response, "text", None))

        # ✅ Extract text safely
        response_text = safe_extract_text(response)
        print("🧾 Extracted Text (first 300 chars):", response_text[:300], "...")

        tool_context.state["model_response"] = response_text

        # ✅ Try JSON parse
        try:
            prompt_list = json.loads(response_text.strip())
        except json.JSONDecodeError:
            print("⚠️ Gemini returned non-JSON format. Using fallback prompt generation.")
            prompt_list = []

        # 🪵 Log full raw response for future debugging
        try:
            log_dir = tool_context.state.get("log_dir", "logs")
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

            raw_log_path = os.path.join(log_dir, f"gemini_raw_response_{ts}.json")

            # Convert response to serializable form
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
                prompt_list.append(f"State key campaign objectives for {brand_name} in {time_period}. Summarize {data_granularity.lower()} ROAS, CTR, and Conversions.")
            elif "Overview" in section_name:
                prompt_list.append(f"Provide performance overview across channels for {brand_name} in {time_period}. Include spend, ROAS, and CTR.")
            elif "Analysis" in section_name:
                prompt_list.append(f"Analyze {data_granularity.lower()} trends for {brand_name} in {time_period}, focusing on ROAS, CTR, and Conversions.")
            elif "Recommendations" in section_name:
                prompt_list.append(f"Suggest actionable optimizations for future campaigns of {brand_name} based on {time_period} insights.")
            elif "Context" in section_name:
                prompt_list.append(f"List campaign IDs, objectives, duration, and spend details for {brand_name}'s {time_period} campaign.")
            else:
                prompt_list.append(f"Summarize key insights for {section_name} of {brand_name}'s {time_period} performance report.")

    # 🔟 Save prompt list & user query with timestamp
    try:
        log_dir = tool_context.state.get("log_dir", "logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        prompt_json_path = os.path.join(log_dir, f"prompt_list_{timestamp}.json")
        with open(prompt_json_path, "w", encoding="utf-8") as f:
            json.dump({"timestamp": timestamp, "session_id": session_id, "prompt_list": prompt_list}, f, indent=2)

        user_query_log = os.path.join(log_dir, f"user_query_{timestamp}.txt")
        with open(user_query_log, "w", encoding="utf-8") as f:
            f.write(f"Timestamp: {timestamp}\nSession ID: {session_id}\nUser Query: {user_query}\n")

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
            "platform": platform,
            "duration": time_period,
            "report_type": report_type,
        },
        "timestamp": datetime.now().isoformat(),
    }
    tool_context.state["prompt_generator_out"] = prompt_list

    print(f"🟢 Generated {len(prompt_list)} prompts successfully.")
    return prompt_list