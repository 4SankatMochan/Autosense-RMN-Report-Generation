import re
import os
import json
from datetime import datetime
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel


async def generate_prompt(tool_context: ToolContext):
    """Dynamically generate structured prompts using persona + persona_report + user_query."""

    print("🧩 Inside Prompt Generator Agent")
    print(f"Session ID: {tool_context._invocation_context.session.id}")

    # 1️⃣ Extract user query text safely
    user_query = str(tool_context.state.get("user_query", "{}"))

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

    # 4️⃣ Fallbacks pulled from state or env
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

    # 8️⃣ Build fusion meta-prompt dynamically
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
    tool_context.state["prompt_type"] = prompt_type
    print("\n🧠 Fusion Prompt ready. Sending to model...")

    # 9️⃣ Safe model handling
    model_name = (
        tool_context.state.get("generator_model")
        or os.getenv("SEQUENTIAL_AGENT")
        or "gemini-2.5-flash"
    )
    if not model_name:
        raise ValueError("❌ No model specified in tool_context.state or environment variable SEQUENTIAL_AGENT.")

    try:
        model = GenerativeModel(model_name)
        response = model.generate_content(fused_prompt, generation_config={"temperature": temperature})
        model_output = response.candidates[0].content.parts[0].text.strip()

        if not model_output:
            raise ValueError("Model returned empty output.")

        # 🔍 Parse output safely
        try:
            generated_prompts = json.loads(model_output)
        except json.JSONDecodeError:
            print("⚠️ Model did not return strict JSON. Using fallback parsing.")
            generated_prompts = [
                line.strip("-• ").replace("Prompt ", "").strip()
                for line in model_output.split("\n")
                if line.strip()
            ]
            generated_prompts = generated_prompts[:prompt_count]

        # 🔒 Log fusion prompt & output
        try:
            log_dir = tool_context.state.get("log_dir", "logs")
            log_file = tool_context.state.get("log_file", "generated_prompts_log.txt")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, log_file)

            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write("\n" + "=" * 80 + "\n")
                log_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"Session ID: {tool_context._invocation_context.session.id}\n")
                log_file.write(f"Model: {model_name}\nTemperature: {temperature}\n")
                log_file.write(f"Persona: {persona_name}\nBrand: {brand_name}\nPlatform: {platform}\n")
                log_file.write(f"Prompt Type: {prompt_type}\nPrompt Count: {prompt_count}\n")
                log_file.write("\n--- Fusion Prompt ---\n")
                log_file.write(fused_prompt + "\n")
                log_file.write("\n--- Model Output ---\n")
                log_file.write(model_output + "\n")
                log_file.write("=" * 80 + "\n")
            print(f"🪵 Logged generated prompts to: {log_path}")
        except Exception as log_err:
            print(f"⚠️ Failed to log generated prompts: {log_err}")

        # ✅ Store and return results
        tool_context.state["prompt_generator_out"] = generated_prompts
        print(f"\n🟢 Total Prompts Generated: {len(generated_prompts)}")

        return {
            "status": "success",
            "prompt_count": len(generated_prompts),
            "prompt_type": prompt_type,
            "parsed": isinstance(generated_prompts, list),
            "model": model_name,
            "temperature": temperature,
        }

    except Exception as e:
        print(f"🔴 Error generating prompts: {e}")
        tool_context.state["prompt_generator_out"] = []
        return {"status": "failed", "error": str(e)}
