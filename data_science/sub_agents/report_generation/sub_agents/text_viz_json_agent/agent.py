"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import Agent
from google.adk.tools import load_artifacts

from .prompts import return_instructions_json
from .tools import text_viz_json

from functools import wraps
import inspect

def single_call_guard(tool_fn):
    @wraps(tool_fn)
    async def wrapper(*args, **kwargs):
        state = kwargs.get("state", {})

        if state.get("tool_called"):
            return {
                "final_answer": True,
                "data": "Tool already called once."
            }

        state["tool_called"] = True

        # 👇 Handle async vs sync properly
        if inspect.iscoroutinefunction(tool_fn):
            result = await tool_fn(*args, **kwargs)
        else:
            result = tool_fn(*args, **kwargs)

        return {
            "final_answer": True,
            "data": result
        }

    return wrapper

guarded_generate_prompt = single_call_guard(text_viz_json)

root_agent = Agent(
    model=os.getenv("TEXT_VIZ_JSON_AGENT"),
    description= "Text viz json agent creates proper json schema for artifacts.",
    instruction= return_instructions_json(),
    name="text_viz_json_agent",
    tools=[guarded_generate_prompt,
        load_artifacts],
)
