from google.adk.tools import ToolContext
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel
from google.genai.types import Part, Blob

async def campaign_comparison_agent(tool_context: Optional[ToolContext] = None, **kwargs):
    
    # result = tool_context.state["campaign_analysis_output"]
    result = tool_context.state.get("campaign_analysis_output")
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


async def run_campaign_comparison(
    aggregated_results: list,
    tool_context: ToolContext
):
   
    model = GenerativeModel(os.getenv("GEMINI_MODEL"))
    response = model.generate_content(
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
            return " No comparison generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"