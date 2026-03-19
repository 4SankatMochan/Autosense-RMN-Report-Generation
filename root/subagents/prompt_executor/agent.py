
"""Agent to call db_ds_agent parallely.
"""
import os
from datetime import date
 
from google.genai import types
 
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import load_artifacts
from google.adk.tools import FunctionTool
from data_science.agent import setup_before_agent_call
 
from .prompts import return_instructions_root
from .tools import call_db_ds_agent, Sequential_Agent
date_today = date.today()
call_db_ds = FunctionTool(func=call_db_ds_agent)
sequential_agent = FunctionTool(func=Sequential_Agent)
 
root_agent = Agent(
    model=os.getenv("ROOT_AGENT_MODEL"),
    name="prompt_executor",
    instruction=return_instructions_root(),
    tools=[
        call_db_ds,
        sequential_agent
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
    # callbacks = [setup_before_agent_call]
)