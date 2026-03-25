from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio
from .subagents.Campaign_analysis.agent import campaign_analysis_root_agent # try another way, might be issue
from .subagents.Campaign_comparison.agent import campaign_comparison_root_agent
from .subagents.Executive_summary.agent import executive_summary_root_agent
from .subagents.Recommendation.agent import recommendation_root_agent
from google.adk.agents.sequential_agent import SequentialAgent
import time
async def agent_call(question, tool_context):
    agent_tool = AgentTool(agent=root_agent)
    db_ds_agent_output = await agent_tool.run_async(
            args={"request": question}, tool_context=tool_context
        )
    return db_ds_agent_output
 
async def call_db_ds_agent(
    tool_context: ToolContext,):
    """Tool to execute prompts"""
    # print("inside prompt executor agent")
    # print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    question_list = tool_context.state.get("prompt_generator_out")
    
    print("Inside db_ds_agent ",question_list)
    # question_list = [
    #     {
    #     "section_name": "Context",
    #     "prompts": [
    #         # "Can you provide the following details for Campaign ID: CMP_2025_0001 and Brand Name: Dove: Campaign Name, Category, Media Types, Channel, Objective, Sub-Objective, Campaign Duration, Planned Budget, and Actual Spend (for the latest date)?"
    #     ]
    #     },
    #     {
    #     "section_name": "Campaign Overview",
    #     "prompts": [
    #         # "For Campaign ID: CMP_2025_0001 and Brand Name: Dove, please provide a high-level campaign summary table including Campaign ID, Campaign Name, Budget (Planned Spend), Campaign Objective, Total Ad Spend, and Budget Utilization.",
    #         # "For Campaign ID: CMP_2025_0001 and Brand Name: Dove, focusing on the 'Consideration' objective, please generate a table summarizing performance by 'Channel'. The table should include 'Total_Ad_Spend', 'Impressions', 'Unique_Reach', and 'Clicks'. When consolidating data for each channel across different dates, sum 'Total_Ad_Spend', 'Impressions', and 'Clicks'. For 'Unique_Reach', use the maximum or distinct value for that channel."
    #     ]
    #     },
    #     {
    #     "section_name": "Campaign-wise Analysis",
    #     "prompts": [
    #         "Show the weekly trend of 'Total_Ad_Spend' by 'Channel' for Campaign ID: CMP_2025_0001 and Brand Name: Dove, specifically for the 'Consideration' objective. Please include a visualization to illustrate these trends.",
    #         "Provide the weekly trend of 'Impressions' by 'Channel' for Campaign ID: CMP_2025_0001 and Brand Name: Dove, for the 'Consideration' objective. A visualization of these trends would be helpful.",
    #         "Illustrate the weekly trend of 'Clicks' by 'Channel' for Campaign ID: CMP_2025_0001 and Brand Name: Dove, targeting the 'Consideration' objective. Please include a visual representation.",
    #         "Generate a concise performance summary for Campaign ID: CMP_2025_0001 and Brand Name: Dove, focusing on the 'Consideration' objective. Highlight key KPI performances, identify any anomalies, and summarize overall and weekly performance trends."
    #     ]
    #     }
    # ]

    flat_prompts = [
    prompt
    for section in question_list
    for prompt in section.get("prompts", [])
    ]
    print(f"prompt generator output: {str(flat_prompts)}")

    tasks = [agent_call(question, tool_context) for question in flat_prompts]
    print("par_callstart",time.strftime('%H:%M:%S'))
    results = await asyncio.gather(*tasks)
    print("par_call_end",time.strftime('%H:%M:%S'))
    print(results)
    tool_context.state["db_ds_agent_output"] = results  
    return "Executed Sucessfully"
 
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
            recommendation_root_agent,
            executive_summary_root_agent
            
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