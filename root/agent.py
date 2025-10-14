import os
from google.genai import types
from google.adk.agents import Agent, LlmAgent
from google.adk.agents.callback_context import CallbackContext
from prompt_executor.agent import root_agent as prompt_executor
from data_science.agent import root_agent as data_science
from prompt_generator_list.agent import root_agent as prompt_generator
from report_generation.agent import root_agent as report_generator
from .prompts import return_instructions_root


def setup_before_agent_call(callback_context: CallbackContext):
    callback_context.state["report_template"] = """Use any template matching the content
"""
    callback_context.state["persona_context"] = """
"""


root_agent = LlmAgent(
    name="Coordinator",
    model=os.getenv("ROOT_AGENT_MODEL"),
    description=return_instructions_root(),
    sub_agents=[ 
        data_science,
        prompt_executor,
        prompt_generator, 
        report_generator
    ],
    before_agent_callback=setup_before_agent_call,
)