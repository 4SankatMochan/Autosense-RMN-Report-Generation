from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio


async def generate_prompt(
    tool_context: ToolContext,
):
    """Tool to call db_ds agent"""
    print("inside prompt generator agent")
    print(f"session id inside generate_prompt tool inside prompt generator: {tool_context._invocation_context.session.id}")
    question_list = ["bar plot for total sales across all the channels", "pie chart for total sales across all the channels"]
    tool_context.state["prompt_generator_out"] = question_list
    return "prompts generated"