from google.adk.tools import ToolContext
from ...sub_agents import ds_agent
from google.adk.tools.agent_tool import AgentTool
import os

async def call_ds_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data science (nl2py) agent."""

    if question == "N/A":
        return tool_context.state["db_agent_output"]

    input_data = tool_context.state["query_result"]

    question_with_data = f"""
  Question to answer: {question}

  Actual data to analyze prevoius quesiton is already in the following:
  {input_data}

  """
    log_file_path = os.path.join(os.getcwd(), "debug_log.txt")
    with open(log_file_path, 'a') as f:
        f.write(f'call is from ds_tool. \n')

    agent_tool = AgentTool(agent=ds_agent)

    ds_agent_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )


    tool_context.state["ds_agent_output"] = ds_agent_output
    return ds_agent_output