"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import Agent
from google.adk.tools import load_artifacts

from .prompts import return_instructions_json
from .tools import generate_report, format_report


root_agent = Agent(
    model=os.getenv("TEXT_VIZ_JSON_AGENT"),
    description= return_instructions_json(),
    instruction= return_instructions_json(),
    name="text_viz_report_summarizer_agent",
    tools=[generate_report,
        format_report,
        load_artifacts],
)
