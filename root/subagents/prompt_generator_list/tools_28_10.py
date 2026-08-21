import re
import os
import json
from datetime import datetime
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel


async def generate_prompt(tool_context: ToolContext):
    """Generate structured Instruction + List of Prompts safely for Campaign Performance Report."""

    print("🧩 Inside Prompt Generator Agent")
    session_id = getattr(tool_context._invocation_context.session, "id", "unknown_session")
    print(f"Session ID: {session_id}")

    # --- CONFIG ---
    use_gemini = bool(tool_context.state.get("use_gemini", True))
    temperature = float(tool_context.state.get("temperature", 0.2))
    model_name = (
        tool_context.state.get("generator_model")
        or os.getenv("SEQUENTIAL_AGENT")
        or "gemini-2.5-flash"
    )

    # 1️⃣ Extract user query
    user_query = str(tool_context.state.get("user_query", "{}")).strip()

    # 2️⃣ Load persona & persona_report safely (accepts dict OR list)
    persona_raw = tool_context.state.get("persona", "{}")
    persona_report_raw = tool_context.state.get("persona_report", "{}")

    def ensure_dict(obj):
        """Safely convert list/string to dict."""
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            # convert [{"persona": "X", ...}] → {"X": {...}}
            try:
                out = {}
                for item in obj:
                    name = item.get("persona") or item.get("name") or "Unknown"
                    out[name] = item
                return out
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

    # 3️⃣ Extract attributes
    available_personas = tool_context.state.get(
        "available_personas",
        ["Client Solution Manager", "Ad Ops Analyst", "Marketing Strategist", "Data Scientist"],
    )
    persona_pattern = "|".join(available_personas)
    persona_match = re.search(fr"(?i)({persona_pattern})", user_query)
    brand_match = re.search(r"for\s+([\w\s]+?)\s+(brand|product)", user_query)
    platform_match = re.search(r"on\s+([\w\s]+)", user_query)
    time_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
        user_query,
    )
    report_type_match = re.search(r"(Campaign Performance Report|Performance Report|Budget Report)", user_query, re.I)

    # 4️⃣ Fallback defaults
    persona_name = persona_match.group(1).strip() if persona_match else tool_context.state.get("default_persona", "Client Solution Manager")
    brand_name = brand_match.group(1).strip() if brand_match else tool_context.state.get("default_brand", "Unknown Brand")
    platform = platform_match.group(1).strip() if platform_match else tool_context.state.get("default_platform", "Unknown Platform")
    time_period = time_match.group(0) if time_match else tool_context.state.get("default_time_period", "N/A")
    report_type = report_type_match.group(1).title() if report_type_match else tool_context.state.get("default_report_type", "Campaign Performance Report")

    # 🪄 Store extracted filters in tool_context.state for downstream agents
    tool_context.state.update({
        "persona_name": persona_name,
        "brand_name": brand_name,
        "platform": platform,
        "time_period": time_period,
        "report_type": report_type,
        "filters": {
            "persona": persona_name,
            "brand": brand_name,
            "platform": platform,
            "duration": time_period,
            "report_type": report_type
        }
    })
    print("🧾 Saved filters into tool_context.state ✅")



    # 5️⃣ Persona context
    persona_data = persona_json.get(persona_name, {})
    persona_tone = persona_data.get("tone", "Professional, concise")
    persona_focus_kpis = persona_data.get("focus_kpis", ["ROAS", "CTR", "Conversions"])

    # 6️⃣ Persona report matrix
    report_obj = (
        persona_report_json
        .get(persona_name, {})
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

    campaign_report = report_schema.get("Campaign_Performance_Report", {})
    report_sections = list(campaign_report.keys())

    # 8️⃣ Build instruction markdown
    instruction_md = f"""**INSTRUCTION**

You are acting as a {persona_name} with a tone described as {persona_tone}.
Use the inputs below to generate prompts for a {report_type}.

**Persona:** {persona_name}

**User Query Filters:**
- Brand: {brand_name}
- Duration: {time_period}
- Platform: {platform}
- Data Granularity: {data_granularity}
- Visualization Preference: {', '.join(visualization_pref)}
- Output Preference: {', '.join(output_pref)}
- Focus KPIs: {', '.join(persona_focus_kpis)}

**Report Sections:**
{chr(10).join([f"{i+1}. {sec}" for i, sec in enumerate(report_sections)])}

**TASK:**
Generate a list of user queries to fill the report sections mentioned above using the information above.
"""

    # 9️⃣ Generate prompts
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
            model = GenerativeModel(model_name)
            response = model.generate_content(fusion_prompt, generation_config={"temperature": temperature})
            prompt_list = json.loads(response.candidates[0].content.parts[0].text.strip())
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}. Using fallback.")
            use_gemini = False

    if not use_gemini or not prompt_list:
        for section_name in report_sections:
            if "Executive" in section_name:
                prompt_list.append(f"State key campaign objectives for {brand_name} in {time_period}. Summarize {data_granularity.lower()} ROAS, CTR, and Conversions.")
            elif "Overview" in section_name:
                prompt_list.append(f"Provide performance overview across channels for {brand_name} in {time_period}. Include spend, ROAS, and CTR.")
            elif "Analysis" in section_name:
                prompt_list.append(f"Analyze performance trends for {brand_name} in {time_period}, focusing on weekly ROAS and CTR.")
            elif "Recommendations" in section_name:
                prompt_list.append(f"Suggest actionable optimizations for future campaigns of {brand_name} based on {time_period} insights.")
            elif "Context" in section_name:
                prompt_list.append(f"List campaign details such as IDs, duration, and objectives for {brand_name}'s {time_period} campaign.")
            else:
                prompt_list.append(f"Summarize key insights for {section_name} of {brand_name}'s {time_period} performance report.")

    # 🔁 Markdown output
    output_md = "**OUTPUT**\n\n**List of Prompts**\n" + "\n".join(
        [f"{i+1}. {p}" for i, p in enumerate(prompt_list)]
    )
    full_markdown = f"{instruction_md}\n---\n\n{output_md}"

    # ✅ Final payload
    output_payload = {
        "status": "success",
        "persona": persona_name,
        "filters": {
            "brand": brand_name,
            "platform": platform,
            "duration": time_period,
            "report_type": report_type,
        },
        "markdown_output": full_markdown,
        "prompt_list": prompt_list,
        "summary": {
            "total_prompts": len(prompt_list),
            "model": model_name if use_gemini else "deterministic",
            "temperature": temperature,
            "use_gemini": use_gemini,
        },
    }

    # 🪵 Logging block
    try:
        log_dir = tool_context.state.get("log_dir", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"generated_prompts_{session_id}.txt")

        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write("\n" + "=" * 80 + "\n")
            log_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Session ID: {session_id}\n")
            log_file.write(f"Model: {model_name}\nTemperature: {temperature}\n")
            log_file.write(f"Persona: {persona_name}\nBrand: {brand_name}\nPlatform: {platform}\n")
            log_file.write(f"Use Gemini: {use_gemini}\n")
            log_file.write("\n--- Instruction Block ---\n")
            log_file.write(instruction_md + "\n")
            log_file.write("\n--- Generated Prompts ---\n")
            for i, p in enumerate(prompt_list, start=1):
                log_file.write(f"{i}. {p}\n")
            log_file.write("=" * 80 + "\n")

        print(f"🪵 Logged generated prompts to: {log_path}")
    except Exception as log_err:
        print(f"⚠️ Failed to log generated prompts: {log_err}")

    tool_context.state["prompt_generator_out"] = output_payload
    print(f"🟢 Generated {len(prompt_list)} report prompts successfully.")
    return output_payload
