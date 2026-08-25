"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import Agent
from google.adk.tools import load_artifacts

from .prompts import return_instructions_json
from .tools import text_viz_json

root_agent = Agent(
    model=os.getenv("TEXT_VIZ_JSON_AGENT"),
    description="Text viz json agent creates proper json schema for artifacts.",
    instruction=return_instructions_json(),
    name="text_viz_json_agent",
    tools=[text_viz_json, load_artifacts],
)