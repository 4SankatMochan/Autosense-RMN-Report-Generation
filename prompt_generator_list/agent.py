
"""Agent to call db_ds_agent parallely.
"""
import os
from datetime import date

from google.genai import types

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import load_artifacts

from .prompts import return_instructions_root
from .tools import generate_prompt
date_today = date.today()

root_agent = Agent(
    model=os.getenv("ROOT_AGENT_MODEL"),
    name="prompt_generator",
    instruction=return_instructions_root(),
    tools=[
        generate_prompt,
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
