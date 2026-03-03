# from data_science.agent import root_agent
# from google.adk.tools import ToolContext
# from google.adk.tools.agent_tool import AgentTool
# import asyncio

# async def agent_call(question, tool_context):
#     agent_tool = AgentTool(agent=root_agent)
#     db_ds_agent_output = await agent_tool.run_async(
#             args={"request": question}, tool_context=tool_context
#         )

# async def call_db_ds_agent(
#     tool_context: ToolContext,
# ):
#     """Tool to execute prompts"""
#     print("inside prompt executor agent")
#     print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    
#     question_list = tool_context.state.get("prompt_generator_out")
#     # question_list = [
#     # "What is the reporting period for this campaign performance analysis?",
#     # "Confirm the brand and manager for whom this report is being prepared."]
#     print(f"prompt generator output: {str(question_list)}")
#     tasks = [agent_call(question, tool_context) for question in question_list]
#     results = await asyncio.gather(*tasks)
#     print(results)
#     tool_context.state["db_ds_agent_output"] = results  
#     return "executed successfully"

from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio
 
async def agent_call(question, tool_context):
    agent_tool = AgentTool(agent=root_agent)
    db_ds_agent_output = await agent_tool.run_async(
            args={"request": question}, tool_context=tool_context
        )
    return db_ds_agent_output

async def call_db_ds_agent(
    tool_context: ToolContext):
    """Tool to execute prompts"""
    print("inside prompt executor agent")
    print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    question_list = tool_context.state.get("prompt_generator_out")

    # flat_prompts = [
    #     prompt
    #     for section_name in question_list
    #     for prompt in section_name.get("prompts", [])
    # ]

    flat_prompts = [
    prompt
    for section in question_list
    for prompt in section.get("prompts", [])
    ]
 
    # question_list= [
    #                 "What customization and filtering options are available for analyzing the performance of Campaign ID: CMP_2025_0007 for Continental? Specifically, list available timelines (e.g., daily, weekly, monthly) and segmentation options (e.g., by creative, channel, audience)."]
    # print(f"prompt generator output: {str(question_list)}")
    tasks = [agent_call(prompt, tool_context) for prompt in flat_prompts]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    final_results = []
    failed_prompts = []

    for prompt, result in zip(flat_prompts, results):
        if isinstance(result, Exception):
            failed_prompts.append({
                "prompt": prompt,
                "error": str(result)
            })
        else:
            final_results.append({
                "prompt": prompt,
                "response": result
            })

    print("SUCCESS:", final_results)
    print("FAILED:", failed_prompts)

    tool_context.state["db_ds_agent_output"] = {
        "success": final_results,
        "failed": failed_prompts
    } 
    
    return "Executed Successfully"

""" For retaining setion name for each prompts also. """

# question_list = tool_context.state.get("prompt_generator_out")

# async def run_section(section):
#     section_name = section.get("section_name")
#     prompts = section.get("prompts", [])

#     tasks = [agent_call(prompt, tool_context) for prompt in prompts]
#     results = await asyncio.gather(*tasks)

#     return section_name, results

# tasks = [run_section(section) for section in question_list]
# section_outputs = await asyncio.gather(*tasks)

# final_output = {name: res for name, res in section_outputs}