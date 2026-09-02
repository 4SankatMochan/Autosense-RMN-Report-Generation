from google.adk.tools import ToolContext
import asyncio
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel
from google.genai.types import Part, Blob

async def campaign_comparison_agent(tool_context: Optional[ToolContext] = None, **kwargs):
    
    # CampaignComparison runs in Phase 1 parallel with CampaignAnalysis, so
    # campaign_analysis_output is not in state yet — read raw db_ds data instead.
    result = tool_context.state.get("db_ds_agent_output", [])
    # campaign comparison agent
    campaign_comparison_output = await run_campaign_comparison(
        result,
        tool_context
    )

    # Store output for downstream agents
    tool_context.state["campaign_comparison_output"] = campaign_comparison_output

    print("Campaign Comparison Completed.")


    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=campaign_comparison_output.encode("utf-8")
        )
    )
    # artifact_name = tool_context.state.get('artifact_name')
    folder_name = "sequential_agent_campaign_comparison_folder"
    text_path = f"{folder_name}_campaign_comparison.txt"

    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)


    return "Campaign Comparison Executed Successfully"


def _to_model_content(data) -> str:
    """Convert list/dict/other to a plain string the model can accept."""
    if isinstance(data, dict):
        return "\n\n".join(
            f"### {k.replace('_', ' ').title()}\n{v}"
            for k, v in data.items()
            if v
        )
    if isinstance(data, list):
        return "\n\n".join(str(item) for item in data if item)
    return str(data) if data else ""


async def run_campaign_comparison(
    aggregated_results,
    tool_context: ToolContext
):
    content = _to_model_content(aggregated_results)
    if not content:
        raise ValueError("Campaign comparison requires DB data but db_ds_agent_output is empty — all DB queries failed or returned None.")

    model = GenerativeModel(os.getenv("GEMINI_MODEL"))
    gen_config = {"temperature": 0.5, "top_p": 1.0, "max_output_tokens": 2048}

    try:
        response = await asyncio.to_thread(
            lambda: model.generate_content(content, generation_config=gen_config)
        )
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No comparison generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"