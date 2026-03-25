from google.adk.tools import ToolContext
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel
from google.genai.types import Part, Blob

async def executive_summary_agent(tool_context: Optional[ToolContext] = None, **kwargs):
    
    # result = tool_context.state["campaign_comparison_output"]
    keys = [
    "campaign_analysis_output",
    "campaign_comparison_output",
    "recommendation_output"
    ]

    result = {key: tool_context.state.get(key) for key in keys}
    # Execute analysis agent
    executive_summary_output = await run_executive_summary(
        result,
        tool_context
    )

    # Store output for downstream agents
    tool_context.state["executive_summary_output"] = executive_summary_output

    print("Executive Summary Completed.")
    
    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=executive_summary_output.encode("utf-8")
        )
    )
    # artifact_name = tool_context.state.get('artifact_name')
    folder_name = "sequential_agent_executive_summary_folder"
    text_path = f"{folder_name}_executive_summary.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)

    return "Executive Summary Executed Successfully"


async def run_executive_summary(
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
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"