from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio
from .subagents.Campaign_analysis.agent import campaign_analysis_root_agent # try another way, might be issue
from .subagents.Campaign_comparison.agent import campaign_comparison_root_agent
from .subagents.Executive_summary.agent import executive_summary_root_agent
from .subagents.Recommendation.agent import recommendation_root_agent
from google.adk.agents.sequential_agent import SequentialAgent
from .prompts import Execution_prompt as EXECUTION_PROMPT
import time
# async def agent_call(question, tool_context):
#     agent_tool = AgentTool(agent=root_agent)
#     db_ds_agent_output = await agent_tool.run_async(
#             args={"request": question}, tool_context=tool_context
#         )
#     return db_ds_agent_output
 
async def agent_call(question, tool_context):
    agent_tool = AgentTool(agent=root_agent)

    # final_prompt = f"""
    # {EXECUTION_PROMPT}

    # User Question:
    # {question}
    # """

    try:
        result = await asyncio.wait_for(
            agent_tool.run_async(
                args={"request": question},
                tool_context=tool_context
            ),
            timeout=120
        )
 
        return {"question": question, "result": result, "success": True}
 
    except Exception as e:
        print("Agent failed:", question, e)
        return {"question": question, "result": None, "success": False}
 
# async def agent_call(question, tool_context):
#     agent_tool = AgentTool(agent=root_agent)
#     try:
#         result = await agent_tool.run_async(
#             args={"request": question}, tool_context=tool_context
#         )
#         return {"question": question, "result": result, "success": True}
#     except Exception as e:
#         return {"question": question, "result": None, "success": False}
   
async def call_db_ds_agent(
    tool_context: ToolContext,):
    """Tool to execute prompts"""
    print("inside prompt executor agent")
    print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    question_list = tool_context.state.get("prompt_generator_out")
#     question_list = [{
#             "section_name": "Context",
#             "prompts": [
#             # "Could you provide the campaign details for Campaign ID CMP_2025_2158 for the brand Lifebuoy, including its unique campaign names, unique campaign ad IDs, category, media types, channels, objective, sub-objective, campaign duration, unique planned spend, and daily actual spend?"
#             ]
#         },
#         {
#             "section_name": "Campaign Overview",
#             "prompts": [
#             # "For Campaign ID CMP_2025_2158 for the brand Lifebuoy, please provide an overview table including the campaign name, planned spend, campaign objective, total ad spend, and spend utilization.",
#             # "What is the range of values observed for Total Ad Spend, Impressions, Reach, Clicks, CTR, CPC, CPCV, and Viewed Units for Campaign ID CMP_2025_2158 for the brand Lifebuoy?",
#             # "Please provide the aggregated values for Total Ad Spend, Impressions, Reach, Clicks, CTR, CPC, CPCV, and Viewed Units, grouped by channel, for Campaign ID CMP_2025_2158 for the brand Lifebuoy."
#             ]
#         },
#         {
#             "section_name": "Campaign-wise Analysis",
#             "prompts": [
#             "Could you provide a daily trend visualization of Total Ad Spend for Campaign ID CMP_2025_2158 for the brand Lifebuoy, focusing on the 'Consideration' objective, do provide plot using viz agent?",
#             "Could you provide a daily trend visualization of Impressions for Campaign ID CMP_2025_2158 for the brand Lifebuoy, focusing on the 'Consideration' objective,do provide plot using viz agent?",
#             "Could you provide a daily trend visualization of Reach for Campaign ID CMP_2025_2158 for the brand Lifebuoy, focusing on the 'Consideration' objective, do provide plot using viz agent?",
#             # "Please provide a concise summary of the overall performance for Campaign ID CMP_2025_2158 for the brand Lifebuoy, highlighting key KPI performance, any observed anomalies, and significant trends."
#             ]
#         }
# ]
    flat_prompts = [
    prompt
    for section in question_list
    for prompt in section.get("prompts", [])
    ]
    print(f"prompt generator output: {str(flat_prompts)}")
 
    flat_prompts_1 =  flat_prompts[:4]
    flat_prompts_2 =  flat_prompts[4:]
 
    print("batch1_start", time.strftime('%H:%M:%S'))
 
    # -------- FIRST BATCH (4 prompts) --------
    tasks_1 = [agent_call(question, tool_context) for question in flat_prompts_1]
    results_1 = await asyncio.gather(*tasks_1)
    print(results_1[:10])
 
    print("batch1_end", time.strftime('%H:%M:%S'))
 
 
    # -------- SECOND BATCH (remaining prompts) --------
    print("batch2_start", time.strftime('%H:%M:%S'))
 
    tasks_2 = [agent_call(question, tool_context) for question in flat_prompts_2]
    results_2 = await asyncio.gather(*tasks_2)
    print(results_2[:10])
 
    print("batch2_end", time.strftime('%H:%M:%S'))
 
 
    #Combine results
    all_results = results_1 + results_2
 
    # -------- THIRD PASS (Retry Failed) --------
    retry_prompts = [
        r["question"] for r in all_results
        if not r["success"] or not r["result"]
    ]
 
    if retry_prompts:
        print("retry_start", time.strftime('%H:%M:%S'))
        print("Retrying:", retry_prompts)
 
        retry_tasks = [agent_call(q, tool_context) for q in retry_prompts]
        retry_results = await asyncio.gather(*retry_tasks)
 
        retry_map = {r["question"]: r for r in retry_results}
 
        for i, r in enumerate(all_results):
            if r["question"] in retry_map and (not r["success"] or not r["result"]):
                all_results[i] = retry_map[r["question"]]
 
        print("retry_end", time.strftime('%H:%M:%S'))
 
    # -------- FINAL OUTPUT --------
    final_results = [r["result"] for r in all_results]
 
    print(final_results)
 
    tool_context.state["db_ds_agent_output"] = final_results
    return "Executed Successfully"
   
# async def Sequential_Agent(question, tool_context: ToolContext):
#     SequentialAgent(
#         name="Sequential_Agent",
#         sub_agents=[campaign_analysis_root_agent,campaign_comparison_root_agent, executive_summary_root_agent, recommendation_root_agent],
#         description="Executes a sequence of code writing, reviewing, and refactoring.", # add this as a wrapper in agent file
#         )# add agent as a tool in agent.py
#     Sequential_agent_output = await SequentialAgent.run_async(
#          args= {'request':"\n".join(tool_context.state["db_ds_agent_output"])}, tool_context=tool_context
#     )
#     tool_context.state[" Sequential_agent_output"] =  Sequential_agent_output
#     return "Executed Sucessfully"
async def Sequential_Agent(tool_context: ToolContext):
 
    sequential_agent = SequentialAgent(
        name="Sequential_Agent",
        sub_agents=[
            campaign_analysis_root_agent,
            campaign_comparison_root_agent,
            executive_summary_root_agent,
            recommendation_root_agent
        ],
        description="Executes campaign analysis pipeline sequentially."
    )
 
    agent_tool = AgentTool(agent=sequential_agent)
 
    input_text = "\n".join(map(str, tool_context.state["db_ds_agent_output"]))
 
    Sequential_agent_output = await agent_tool.run_async(
        args={"request": input_text},
        tool_context=tool_context
    )
 
    tool_context.state["Sequential_agent_output"] = Sequential_agent_output
 
    return "Executed Successfully"