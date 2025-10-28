import re
import os
import json
from datetime import datetime
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel


async def generate_prompt(tool_context: ToolContext):
    """Dynamically generate structured prompts using persona + persona_report + local report schema."""

    print("🧩 Inside Prompt Generator Agent")
    session_id = getattr(tool_context._invocation_context.session, "id", "unknown_session")
    print(f"Session ID: {session_id}")

    # 1️⃣ Extract user query text safely
    user_query = str(tool_context.state.get("user_query", "{}")).strip()

    # 2️⃣ Load persona & persona_report safely
    try:
        persona_json = json.loads(tool_context.state.get("persona", "{}"))
        persona_report_json = json.loads(tool_context.state.get("persona_report", "{}"))
    except Exception as e:
        print(f"⚠️ Failed to parse persona context: {e}")
        persona_json, persona_report_json = {}, {}

    # 3️⃣ Extract available personas and report types dynamically
    available_personas = tool_context.state.get(
        "available_personas",
        ["Client Solution Manager", "Ad Ops Analyst", "Marketing Strategist", "Data Scientist"],
    )
    available_reports = tool_context.state.get(
        "available_report_types",
        ["performance report", "budget report", "summary report", "optimization report"],
    )

    persona_pattern = "|".join(available_personas)
    report_pattern = "|".join(available_reports)

    persona_match = re.search(fr"(?i)({persona_pattern})", user_query)
    brand_match = re.search(r"for the\s+([\w\s]+?)\s+(brand|product)", user_query)
    platform_match = re.search(r"on\s+([\w\s]+)", user_query)
    time_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
        user_query,
    )
    report_type_match = re.search(fr"(?i)({report_pattern})", user_query)

    # 4️⃣ Fallback defaults
    persona_name = persona_match.group(1).strip() if persona_match else tool_context.state.get("default_persona", "Client Solution Manager")
    brand_name = brand_match.group(1).strip() if brand_match else tool_context.state.get("default_brand", "Unknown Brand")
    platform = platform_match.group(1).strip() if platform_match else tool_context.state.get("default_platform", "Unknown Platform")
    report_type = report_type_match.group(1).title() if report_type_match else tool_context.state.get("default_report_type", "Campaign Performance Report")
    time_period = time_match.group(0) if time_match else tool_context.state.get("default_time_period", "N/A")

    # 5️⃣ Persona & report context defaults
    persona_data = persona_json.get(persona_name, {})
    persona_tone = persona_data.get("tone", tool_context.state.get("default_tone", "Professional, concise"))
    persona_focus_kpis = persona_data.get("focus_kpis", tool_context.state.get("default_focus_kpis", ["ROAS", "CTR", "Conversions"]))

    report_obj = (
        persona_report_json
        .get(persona_name, {})
        .get("objectives", {})
        .get(report_type, {})
    )
    data_granularity = report_obj.get("data_granularity", tool_context.state.get("default_data_granularity", "Monthly"))
    visualization_pref = report_obj.get("visualization_pref", tool_context.state.get("default_visualization_pref", ["Charts", "KPIs"]))
    output_pref = report_obj.get("output_pref", tool_context.state.get("default_output_pref", ["Slide Deck + Report"]))

    # 6️⃣ Determine prompt type (T2T or T2P)
    prompt_type = "T2P" if any(word in user_query.lower() for word in ["chart", "plot", "visual", "trend", "graph"]) else "T2T"

    # 7️⃣ Dynamic prompt count & temperature
    prompt_count = int(tool_context.state.get("prompt_count", 3))
    temperature = float(tool_context.state.get("temperature", 0.01))

    # 8️⃣ Load local report schema (case-insensitive folder safety)
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

    # 9️⃣ Build section-wise DB prompts
    section_prompts = {}
    campaign_report = report_schema.get("Campaign_Performance_Report", {})

    for section_name, section_content in campaign_report.items():
        prompt_text = f"""
As a {persona_name} with a tone described as {persona_tone},
generate a SQL query or data retrieval instruction for the "{section_name}" section
of the {report_type} for {brand_name} on {platform}, covering {time_period}.

Context:
- Focus KPIs: {', '.join(persona_focus_kpis)}
- Data Granularity: {data_granularity}
- Visualization Preference: {', '.join(visualization_pref)}
- Output Preference: {', '.join(output_pref)}

Objective:
Extract all fields relevant to this section ({', '.join(section_content.keys()) if isinstance(section_content, dict) else 'N/A'})
to populate the report dynamically.
"""
        section_prompts[section_name] = prompt_text.strip()

    print(f"🧾 Generated {len(section_prompts)} section-level DB prompts.")
    # 🔍 Debug printout
    print("\n================= 🧠 SECTION-WISE PROMPTS =================")
    for section_name, prompt_text in section_prompts.items():
        print(f"\n📘 Section: {section_name}")
        print("-" * (len(section_name) + 10))
        print(prompt_text[:800])
        print("------------------------------------------------------------")
    print("================= ✅ END OF SECTION PROMPTS =================\n")

    # 🔟 Build Fusion meta-prompt
    fused_prompt = f"""
You are acting as a {persona_name} with a tone described as {persona_tone}.
Create {prompt_count} structured prompts for a {report_type} for the {brand_name} brand on {platform}, covering {time_period}.

Context:
- Focus KPIs: {', '.join(persona_focus_kpis)}
- Data Granularity: {data_granularity}
- Visualization Preference: {', '.join(visualization_pref)}
- Output Preference: {', '.join(output_pref)}
- Prompt Type: {prompt_type}

Ensure prompts cover: campaign objectives, KPI trends, budget insights, ROI analysis, and recommendations.
Return only this JSON format:
["Prompt 1: ...", ..., "Prompt {prompt_count}: ..."]
"""

    tool_context.state["fused_prompt"] = fused_prompt
    tool_context.state["section_prompts"] = section_prompts
    tool_context.state["prompt_type"] = prompt_type

    # 🔥 Model for fusion prompt generation
    model_name = (
        tool_context.state.get("generator_model")
        or os.getenv("SEQUENTIAL_AGENT")
        or "gemini-1.5-pro"
    )
    if not model_name:
        raise ValueError("❌ No model specified in tool_context.state or environment variable SEQUENTIAL_AGENT.")

    try:
        model = GenerativeModel(model_name)
        response = model.generate_content(fused_prompt, generation_config={"temperature": temperature})
        model_output = response.candidates[0].content.parts[0].text.strip()

        try:
            fusion_prompts = json.loads(model_output)
        except json.JSONDecodeError:
            print("⚠️ Model did not return strict JSON. Fallback parsing applied.")
            fusion_prompts = [
                line.strip("-• ").replace("Prompt ", "").strip()
                for line in model_output.split("\n")
                if line.strip()
            ][:prompt_count]

        # 🪵 Log results safely
        log_dir = tool_context.state.get("log_dir", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "generated_prompts_log.txt")
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write("\n" + "=" * 80 + "\n")
            log_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Session ID: {session_id}\n")
            log_file.write(f"Model: {model_name}\nTemperature: {temperature}\n")
            log_file.write(f"Persona: {persona_name}\nBrand: {brand_name}\nPlatform: {platform}\n")
            log_file.write(f"Prompt Count: {prompt_count}\nPrompt Type: {prompt_type}\n")
            log_file.write("\n--- Fusion Prompt ---\n")
            log_file.write(fused_prompt + "\n")
            log_file.write("\n--- Model Output ---\n")
            log_file.write(model_output + "\n")
            log_file.write("=" * 80 + "\n")

        print(f"🪵 Logged generated prompts to: {log_path}")

        output_payload = {
            "status": "success",
            "fusion_prompts": fusion_prompts,
            "section_prompts": section_prompts,
            "summary": {
                "fusion_count": len(fusion_prompts),
                "section_count": len(section_prompts),
                "total_prompts": len(fusion_prompts) + len(section_prompts),
                "prompt_type": prompt_type,
                "model": model_name,
                "temperature": temperature,
            },
        }

        tool_context.state["prompt_generator_out"] = output_payload
        print(f"\n🟢 Total Prompts Generated: {output_payload['summary']['total_prompts']}")
        return output_payload

    except Exception as e:
        print(f"🔴 Error generating prompts: {e}")
        tool_context.state["prompt_generator_out"] = []
        return {"status": "failed", "error": str(e)}
