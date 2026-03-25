from google.adk.tools import ToolContext
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel
from google.genai.types import Part, Blob

async def recommendation_agent(tool_context: Optional[ToolContext] = None, **kwargs):
    
    # result = tool_context.state["executive_summary_output"]
    keys = [
    "campaign_analysis_output",
    "campaign_comparison_output"
    ]

    result = {key: tool_context.state.get(key) for key in keys}
    # campaign comparison agent
    recommendation_output = await run_recommendation(
        result,
        tool_context
    )

    # Store output for downstream agents
    tool_context.state["recommendation_output"] = recommendation_output

    print("Recommendation Completed.")

    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=recommendation_output.encode("utf-8")
        )
    )
    # artifact_name = tool_context.state.get('artifact_name')
    folder_name = "sequential_agent_recommendation_sequential_folder"
    text_path = f"{folder_name}_recommendation_sequential_agent.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)

    return "Recommendation Executed Successfully"


def _select_recommendation_model_name():
    candidate_models = [
        os.getenv("GEMINI_MODEL"),
        os.getenv("RECOMMENDATION_MODEL"),
        "gemini-1.5-pro",
        "gemini-1.5-mini",
        "gemini-1.5",
        "gemini-1.0",
        "gemini-1.5-flash",
    ]

    seen = set()
    for candidate in candidate_models:
        if not candidate:
            continue
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            GenerativeModel(candidate)
            return candidate
        except Exception as e:
            print(f"⚠️ Model candidate '{candidate}' unavailable: {e}")
            continue

    # If no candidate is available, fallback to a safe default.
    return "gemini-1.5-pro"


async def run_recommendation(
    aggregated_results: list,
    tool_context: ToolContext
):
    model_name = _select_recommendation_model_name()
    print(f"🤖 Using recommendation model: {model_name}")
    model = GenerativeModel(model_name)

    try:
        response = model.generate_content(
            aggregated_results,
            generation_config={
                "temperature": 0.5,
                "top_p": 1.0,
                "max_output_tokens": 2048
            }
        )

        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No comparison generated. Check LLM output or token limit."
        return output_text

    except Exception as e:
        print(f"⚠️ Recommendation generation failed: {e}")
        return f" Error generating recommendation: {e}"