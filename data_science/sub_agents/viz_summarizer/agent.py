"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import Agent
from google.adk.tools import load_artifacts

from .prompts import return_instructions_dv_smry
from .tools import viz_artifact_formatter


root_agent = Agent(
    model=os.getenv("CHART_SUMMARY_MODEL"),
    description= "Visualization Summarizer takes is used to put chart artifact data in a proper json format.",
    instruction= return_instructions_dv_smry(),
    name="chart_summarizer_agent",
    tools=[viz_artifact_formatter,
        load_artifacts],
)
