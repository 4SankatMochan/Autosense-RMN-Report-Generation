
from google.adk.agents import Agent
from google.genai import types
from .prompts import instructions
from .tools import  mark_clarification,set_perceived_query,approve_query,auto_approve_query


agent_tools = [
    mark_clarification,
    set_perceived_query,
    approve_query,
    auto_approve_query
]

root_agent = Agent(
    name="query_validation_agent_v1",
    model="gemini-2.5-flash",
    description="Helps users refine and confirm their queries before execution.",
    instruction=instructions(),
    tools=agent_tools,
    generate_content_config=types.GenerateContentConfig(temperature=0.3),
    disallow_transfer_to_parent=True
)

