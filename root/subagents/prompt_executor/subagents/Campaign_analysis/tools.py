# from .agent import campaign_analysis_root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import json
from google.cloud import storage
import base64
import re
from collections import defaultdict
from typing import List, Optional
import os
import asyncio
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


async def run_campaign_analysis(
    aggregated_results: list,
    tool_context: ToolContext
):
    """
    Executes the Campaign Analysis agent on aggregated DB results
    while conditioning on the original user question.
    """
    model = GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    response = await asyncio.to_thread(
        model.generate_content,
        aggregated_results,
        generation_config={
            "temperature": 0.5,
            "top_p": 1.0,
            "max_output_tokens": 2048
        }
    )

    try:
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"
    
