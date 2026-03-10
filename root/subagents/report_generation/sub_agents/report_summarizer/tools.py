from google import genai
from google.genai import types
from root.subagents.prompt_executor.subagents.Executive_summary import prompt
from .prompts import generate_report_prompt, format_report_prompt
from typing import List, Optional
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel
from pathlib import Path
import json
import os
from datetime import datetime

def timestamped_filename(base_name: str, ext: str) -> str:
    """
    Generates a timestamped filename.
    Example: timestamped_filename('report_markdown', 'md')
    -> 'report_markdown_20251029_144530.md'
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{ts}.{ext}"


def load_report_inputs(tool_context=None, auto_handle=True):
    """
    Load the report template, summary, context, and filters.
    - If auto_handle=True:
        1. Checks tool_context.state for available values.
        2. Falls back to reading files and local defaults.
    - If auto_handle=False:
        Uses only local static file references and strings defined below.

    Returns:
        (template_text, summary_text, context_text, filters_value)
    """

    print(f"\n[load_report_inputs] Auto-handle mode: {auto_handle}")
    state = getattr(tool_context, "state", {}) if tool_context else {}

    base_dir = Path(__file__).parent
    template_path = base_dir / "Campaign_Performance_Report_Template.md"
    summary_path = base_dir / "Campaign_Performance_Summary_Text_Viz.json"

    # Default local context text
    local_context = """This report is prepared for the Marketing and Sales leadership team to provide a comprehensive overview of campaign performance across different channels. The primary objective is to understand which channels contribute most effectively to attributed sales and to identify overall daily sales patterns. The insights derived from this analysis will be crucial in informing strategic decisions related to optimizing future marketing spend, resource allocation, and campaign targeting to maximize ROI.
"""
    local_filters = "nil"

    # Default template and summary if manual flag (auto_handle=False)
    if not auto_handle:
        print("[load_report_inputs] Using manual (local) references only.")
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path.resolve()}")
        if not summary_path.exists():
            raise FileNotFoundError(f"Summary JSON not found: {summary_path.resolve()}")

        template = template_path.read_text(encoding="utf-8")
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_json = json.load(f)
        summary = json.dumps(summary_json, indent=4, ensure_ascii=False)
        print(f"Template loaded ✅ length: {len(template)}")
        print(f"Summary loaded ✅ keys: {list(summary_json.keys())}")
        return template, summary, local_context, local_filters

    # --- Auto handle mode ---
    # Prefer values from tool_context.state when available
    template_text = None
    summary_text = None
    context_text = None
    filters_value = None

    print(f"Load report filters from state: {state.get('report_filters')}")
    # print(f"State keys: {list(state.keys())}")

    # if isinstance(state, dict):
    #     print("In report summarizer, state keys are:dict_keys:")

    template_text = state.get("report_template")
    summary_text = state.get("text_viz_json")
    context_text = state.get("report_context")
    filters_value = state.get("report_filters")

    # Fallback to file-based loading if missing
    if not template_text:
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path.resolve()}")
        template_text = template_path.read_text(encoding="utf-8")

    if not summary_text:
        if not summary_path.exists():
            raise FileNotFoundError(f"Summary JSON not found: {summary_path.resolve()}")
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_json = json.load(f)
        summary_text = json.dumps(summary_json, indent=4, ensure_ascii=False)

    if not context_text:
        context_text = local_context

    # if not filters_value:
    #     filters_value = local_filters

    print(f"[load_report_inputs] Template length: {len(template_text)}")
    print(f"[load_report_inputs] Summary length: {len(summary_text)}")
    print(f"[load_report_inputs] Context length: {len(context_text)}")
    print(f"[load_report_inputs] Filters: {filters_value}")

    return template_text, summary_text, context_text, filters_value

def llm_call(prompt: str, tool_context=None) -> str:
    model = GenerativeModel(os.getenv("TEXT_VIZ_JSON_AGENT"))
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.5,
            # "top_p": 1.0,
            # "max_output_tokens": 7168
        }
    )
    # print(f"llm response")
    # print(response)
    try:
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"

async def generate_markdown_report(tool_context: Optional[ToolContext] = None):
    """ 
    Generates report in Markdown format.
    """
    print("inside report summarization agent")
    print("inside generate markdown report tool")

    template, summary, context, filters = load_report_inputs(tool_context, auto_handle=True)

    print("report template:")
    print(template)

    print("report summary:")
    print(summary)

    print("report context:")
    print(context)

    print("report filters:")    
    print(filters)

    if isinstance(filters, dict):
        persona = filters.get('persona', 'N/A')
        brand = filters.get('brand', 'N/A')
        campaign_id = filters.get('campaign_id', 'N/A')
        period = filters.get('duration', 'N/A')
        report_type = filters.get('report_type', 'N/A')
    else:
        # default fallback when filters is a simple string like "nil"
        persona = brand = campaign_id = period = report_type = 'N/A'

    filter_text = f"""**Filters:**
    Persona: {persona}
    Brand: {brand}
    Campaign ID: {campaign_id}
    Period: {period}
    Report Type: {report_type}
    """
    
    # filters = tool_context.state.get['report_filters']
    # debug prints to verify the inputs being passed to the LLM
    print(f"text_viz_json output: {summary}")
    print(f"report template passed: {template}")
    print(f"report context passed: {context}")
    print(f"report filters passed: {filter_text}")

    # Generate report markdown using LLM
    main_prompt = generate_report_prompt()

    # get viz json from tool state
    text_viz_json = tool_context.state.get("text_viz_json", "")

    custom_prompt = f"""
    **Task**
    Generate report based on the below information.

    **Input Parameters:**

    1. **Text and Visualization Summary:**
    {summary}

    2. **Report Template:**
    {template}

    3. **Report Context:**
    {context}

    4. **Filters:**
    {filter_text}

    5. **Text and Visualization Summary (JSON format)**
    {text_viz_json}

    **Output:**
    """

    prompt = main_prompt + custom_prompt

    res = llm_call(prompt, tool_context=tool_context)

    # Save the llm result in a file for debugging and traceability
    filename = timestamped_filename("report_markdown_debug", "txt")
    root = os.getcwd()
    path = os.path.join(root, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(res)

    tool_context.state['report_markdown'] = res
    print("report markdown generated:")
    print(res)


    # --- Save generated Markdown report to file ---
    try:
        # filename = "report_markdown.md"
        filename = timestamped_filename("report_markdown", "md")
        root = os.getcwd()
        path = os.path.join(root, filename)

        # Ensure text is serializable
        report_text = str(res) if not isinstance(res, str) else res
        with open(path, "w", encoding="utf-8") as f:
            f.write(report_text)

        print(f"✅ Report Markdown saved to: {path}")

    except Exception as e:
        print(f"⚠️ Error saving Markdown file: {e}")

    return "report markdown generated"
  

async def format_report(tool_context: Optional[ToolContext] = None):
    """
    Convert Report from markdown format to JSON format
    """
    print("inside format report tool")
    report = tool_context.state['report_markdown']
    main_prompt = format_report_prompt()
    custom_prompt = f"""
    **Task**
    Generate JSON from the Report given below. Do not violate safety filters while generating output. Remove just the things that violate safety rules and kept  of all the information in the Report.

    **Report:**

    {report}

    **Output:**
    """
    prompt = main_prompt + custom_prompt
    res = llm_call(prompt, tool_context=tool_context)
    # res = ReportSchema.model_validate(res)
    tool_context.state['report_json'] = res
    print("report json generated: ")

    filename = timestamped_filename("report_json", "json")
    # filename = "report_json.json"
        # Save to file in repo root (current working directory)
    root = os.getcwd()
    path = os.path.join(root, filename)

    # If `res` is not a JSON string, try to convert/pretty-print
    report_text = res
    try:
        if isinstance(res, (dict, list)):
            report_text = json.dumps(res, ensure_ascii=False, indent=2)
        else:
            # try to load and pretty print if it's a JSON string
            try:
                parsed = json.loads(res)
                report_text = json.dumps(parsed, ensure_ascii=False, indent=2)
            except Exception:
                # leave as-is (string)
                report_text = str(res)
    except Exception:
        report_text = str(res)

    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"Report JSON saved to: {path}")
    return "report formatted to json"