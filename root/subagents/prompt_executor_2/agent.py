
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
from google.adk.agents.sequential_agent import SequentialAgent
from .subagents.Campaign_analysis.agent import campaign_analysis_root_agent 
from .subagents.Campaign_comparison.agent import campaign_comparison_root_agent
from .subagents.Executive_summary.agent import executive_summary_root_agent
from .subagents.Recommendation.agent import recommendation_root_agent

from .prompts import return_instructions_root
from .tools import call_db_ds_agent, Sequential_Agent

date_today = date.today()
call_db_ds = FunctionTool(func=call_db_ds_agent)
sequential_agent = FunctionTool(func=Sequential_Agent)

# Sequential flow 
Sequential_Agent = SequentialAgent(
    name="Sequential_Agent",
    sub_agents=[campaign_analysis_root_agent,campaign_comparison_root_agent, executive_summary_root_agent, recommendation_root_agent],
    description="Executes a sequence of code writing, reviewing, and refactoring.", # add this as a wrapper in agent file 
)

# agent_tool = AgentTool(agent=Sequential_Agent)

# Sequential_agent_output = await agent_tool.run_async(
#         args= {'request':"\n".join(tool_context.state["db_ds_agent_output"])}, tool_context=tool_context
# )
# tool_context.state[" Sequential_agent_output"] =  Sequential_agent_output


root_agent = Agent(
    model=os.getenv("ROOT_AGENT_MODEL"),
    name="prompt_executor",
    instruction=return_instructions_root(),
    tools=[
        call_db_ds
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
    # callbacks = [setup_before_agent_call]
)
