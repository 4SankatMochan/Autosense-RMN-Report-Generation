
"""Agent to call db_ds_agent parallely.
"""
import os
import time
import logging
from datetime import date

from google.genai import types

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import load_artifacts
from google.adk.tools import FunctionTool

from .prompts import return_instructions_root
from .tools import call_db_ds_agent, Sequential_Agent

date_today = date.today()
logger = logging.getLogger(__name__)

call_db_ds = FunctionTool(func=call_db_ds_agent)
sequential_agent = FunctionTool(func=Sequential_Agent)


def stage2_before_agent_call(callback_context: CallbackContext):
    callback_context.state['stage2_start_perf'] = time.perf_counter()
    logger.info("Stage 2 — Prompt Execution starting")


def stage2_after_agent_call(callback_context: CallbackContext):
    t = time.perf_counter()
    callback_context.state['stage2_end_perf'] = t
    start = callback_context.state.get('stage2_start_perf', t)
    logger.info("Stage 2 — Prompt Execution done in %.1f s", t - start)


root_agent = Agent(
    model=os.getenv("ROOT_AGENT_MODEL"),
    name="prompt_executor",
    instruction=return_instructions_root(),
    tools=[call_db_ds, sequential_agent],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
    before_agent_callback=stage2_before_agent_call,
    after_agent_callback=stage2_after_agent_call,
)