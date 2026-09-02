"""Stage 3 — Report Generation pipeline (direct tool calls, single LLM routing step)."""
import os
import time
import logging
import asyncio
from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext

from .sub_agents.text_viz_json_agent.tools import text_viz_json
from .sub_agents.report_summarizer.tools import generate_markdown_report, format_report
from .sub_agents.pdf_generator.tools import generate_pdf_report

logger = logging.getLogger(__name__)
def setup_before_agent_call(callback_context: CallbackContext):
    callback_context.state["persona_context"] = """
"""
    # callback_context.state["session_id"] = callback_context._invocation_context.session.id
    print(f"inside report gen seq agent: session id from invocation context {callback_context._invocation_context.session.id}")
    print("report starttime",time.strftime('%H:%M:%S'))
    callback_context.state["session_id"] = callback_context._invocation_context.session.id
    callback_context.state["user_id"] = callback_context._invocation_context.user_id
    print(f"inside report gen seq agent: session id from state {callback_context.state["session_id"]}")
    # model = GenerativeModel(os.getenv("SEQUENTIAL_AGENT"))
    # query = callback_context.user_content.parts[0].text
    # prompt = f"""
    #             You are a binary classifier. Your job is to determine whether a user query is requesting a report to be generated from the *current session data*.
    #             Return only one of two values: `True` or `False`.
    #             Respond `True` **only** if the user is asking to generate a report (in any wording) from the *current session*, *this conversation*, or *recent interaction*. It can include phrases like "regenerate report", "create report from this session", "generate summary of our current session", etc.
    #             In all other cases, return `False`.
    #             ### Examples:
    #             User: "Regenerate report from current session"  
    #             Output: True
    #             User: "Can you generate a summary of what we've discussed so far?"  
    #             Output: True
    #             User: "Make a report using this session's data"  
    #             Output: True
    #             User: "Create a new report using uploaded file"  
    #             Output: False
    #             User: "Generate monthly sales report for August"  
    #             Output: False
    #             User: "Summarize the uploaded CSV file"  
    #             Output: False
    #             User: "Give me a quick overview of our current chat"  
    #             Output: True
    #             User: "Please create a new report based on the CRM export"  
    #             Output: False
    #             User: "Draft a report using this conversation"  
    #             Output: True
    #             User: "Send the latest report from the database"  
    #             Output: False
    #             User: "Generate bar chart/report showing ... "
    #             Output : False
    #             Now classify the following user input:
    #             # User: {query}

    #             Output:


    # """
    # response = model.generate_content(
    #         prompt,
    #     generation_config={
    #         "temperature": 0.01,
    #     })
    # with open("debug_log.txt", "a") as f:
    #     f.write(f"user query :{query} \n")
    #     # f.write(f"response from report generator: {response}\n")
    #     f.write(f"{response.candidates[0].content.parts[0].text.strip()}")
    # res = response.candidates[0].content.parts[0].text.strip()
    # if res.lower()=='true':
    #     return None
    # else:
    #     return types.Content(
    #         role="model",
    #         parts=[types.Part(text="I’m sorry, but your request doesn't appear to be about generating a session report. Agent not triggered.")]
    #     )

def stage3_after_agent_call(callback_context: CallbackContext):
    t = time.perf_counter()
    callback_context.state['stage3_end_perf'] = t
    start = callback_context.state.get('stage2_end_perf', t)
    logger.info("Stage 3 — Report Generation done in %.1f s", t - start)


async def run_report_pipeline(tool_context: ToolContext):
    """Execute the full report pipeline in a single tool call.

    Replaces 3 sequential LlmAgents (text_viz_json → report_summarizer → pdf_generator)
    with direct function calls, saving 2 Gemini routing round-trips.

    Execution order (each step is data-dependent on the previous):
      1. text_viz_json            — scans GCS artifacts, populates state['text_viz_json']
      2. generate_markdown_report — LLM call, populates state['report_markdown']
      3. format_report            — parses markdown → JSON, populates state['report_json']
      4. generate_pdf_report      — builds PDF, uploads to GCS, returns (gcs_path, https_url)
    """
    await text_viz_json(tool_context=tool_context)
    await generate_markdown_report(tool_context=tool_context)
    await format_report(tool_context=tool_context)
    result = await generate_pdf_report(tool_context=tool_context)

    # Surface the clickable PDF URL so the LlmAgent includes it in its response.
    if isinstance(result, tuple):
        gcs_path, clickable_url = result
        tool_context.state['report_pdf_url'] = clickable_url
        return (
            f"Report generated successfully.\n\n"
            f"PDF download link: {clickable_url}\n\n"
            f"GCS path: {gcs_path}"
        )
    return f"Report pipeline complete. {result}"


root_agent = LlmAgent(
    model=os.getenv("PDF_GENERATOR_AGENT_MODEL", "gemini-2.5-flash"),
    description="Report Generation Agent — collects artifacts, generates markdown, formats JSON, and produces the final PDF.",
    name="report_generation_agent",
    instruction=(
        "Call run_report_pipeline to execute the complete report generation pipeline. "
        "After the tool returns, copy its output EXACTLY into your response — "
        "do NOT paraphrase or omit any part of it. "
        "The tool output contains the PDF download link which the user must see verbatim."
    ),
    tools=[run_report_pipeline],
    before_agent_callback=setup_before_agent_call,
    after_agent_callback=stage3_after_agent_call,
)

    # before_agent_callback=setup_before_agent_call,