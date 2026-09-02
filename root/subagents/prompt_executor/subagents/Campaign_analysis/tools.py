from google.adk.tools import ToolContext
import asyncio
import json
from google.cloud import storage
import base64
import re
from collections import defaultdict
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel
from google.genai.types import Part, Blob


async def campaign_analysis_agent(tool_context: Optional[ToolContext] = None, **kwargs):

    result = tool_context.state["db_ds_agent_output"]
    print(result)
    # Execute analysis agent
    campaign_analysis_output = await run_campaign_analysis(
        result,
        tool_context
    )

    # Store output for downstream agents

    tool_context.state["campaign_analysis_output"] = campaign_analysis_output

    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=campaign_analysis_output.encode("utf-8")
        )
    )
    
    # artifact_name = tool_context.state.get('artifact_name')
    folder_name = "sequential_agent_campaign_analysis_folder"
    text_path = f"{folder_name}_campaign_analysis.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)
    # text_artifact = Part(
    # inline_data=Blob(
    #     mime_type="text/plain",
    #     data=campaign_analysis_output.encode("utf-8")
    #     )
    # )

    # folder_name = "sequential_agent_campaign_analysis_folder"
    # file_name = "campaign_analysis.txt"

    # artifact_path = f"{folder_name}/{file_name}"

    # await tool_context.save_artifact(
    #     filename=artifact_path,
    #     artifact=text_artifact
    # )
    print("Artifact saved:", text_path)
    print("Text Artifacts:", text_artifact)
    print("Campaign Analysis Completed.")

    return "Campaign Analysis Executed Successfully"


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


async def run_campaign_analysis(
    aggregated_results,
    tool_context: ToolContext
):
    content = _to_model_content(aggregated_results)
    if not content:
        raise ValueError("Campaign analysis requires DB data but db_ds_agent_output is empty — all DB queries failed or returned None.")

    model = GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    gen_config = {"temperature": 0.5, "top_p": 1.0, "max_output_tokens": 2048}

    try:
        response = await asyncio.to_thread(
            lambda: model.generate_content(content, generation_config=gen_config)
        )
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"
    
