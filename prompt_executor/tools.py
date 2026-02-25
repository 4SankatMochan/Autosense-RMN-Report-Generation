from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio

async def agent_call(question, tool_context):
    agent_tool = AgentTool(agent=root_agent)
    db_ds_agent_output = await agent_tool.run_async(
            args={"request": question}, tool_context=tool_context
        )


async def call_db_ds_agent(
    tool_context: ToolContext,
):
    """Tool to execute prompts"""
    print("inside prompt executor agent")
    print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    
    # question_list = tool_context.state.get("prompt_generator_out")
    question_list = [
    "What is the reporting period for this campaign performance analysis?",
    "Confirm the brand and manager for whom this report is being prepared."]
    print(f"prompt generator output: {str(question_list)}")
    tasks = [agent_call(question, tool_context) for question in question_list]
    results = await asyncio.gather(*tasks)
    print(results)
    tool_context.state["db_ds_agent_output"] = results  
    return "executed successfully"