from google.adk.tools import ToolContext
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel

async def recommendation_agent(tool_context: Optional[ToolContext] = None, **kwargs):
    
    # result = tool_context.state["executive_summary_output"]
    result =  tool_context.state.get("executive_summary_output")
    # campaign comparison agent
    recommendation_output = await run_recommendation(
        result,
        tool_context
    )

    # Store output for downstream agents
    tool_context.state["recommendation_output"] = recommendation_output

    print("Recommendation Completed.")

    return "Recommendation Executed Successfully"


async def run_recommendation(
    aggregated_results: list,
    tool_context: ToolContext
):
   
    model = GenerativeModel(os.getenv("ROOT_AGENT_MODEL"))
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