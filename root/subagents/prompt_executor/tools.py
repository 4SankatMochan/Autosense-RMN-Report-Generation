from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio
from .subagents.Campaign_analysis.agent import campaign_analysis_root_agent # try another way, might be issue 
from .subagents.Campaign_comparison.agent import campaign_comparison_root_agent
from .subagents.Executive_summary.agent import executive_summary_root_agent
from .subagents.Recommendation.agent import recommendation_root_agent
from google.adk.agents.sequential_agent import SequentialAgent
import concurrent.futures
from uuid import uuid4
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
    print("inside prompt executor agent")
    print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    question_list = tool_context.state.get("prompt_generator_out")
#     question_list= [
#         # "Provide the complete contextual details for Campaign ID CMP_2025_2158 for brand Lifebuoy, including its name, category, media types, channels, primary and sub-objectives, campaign manager, duration, planned budget, and actual spend to date.",
#         # "What are the available filtering and customization options for analyzing the performance of Campaign ID CMP_2025_2158 (Lifebuoy), specifically regarding timeline granularity and creative segmentation by channel?",
#         # "Generate a high-level summary table for Campaign ID CMP_2025_2158 (Lifebuoy). Include Campaign ID, Campaign Name, Planned Budget, Campaign Objective, Total Ad Spend, and Budget Utilization.",
#         # "Based on the objective of Campaign ID CMP_2025_2158 (Lifebuoy), provide a detailed performance table. For an 'Awareness' objective, include Channel, Total Ad Spend, Impressions, Unique Reach, Frequency, ROAS, and CPM. For a 'Conversion' objective, include Channel, Total Ad Spend, Conversions, Conversion Rate, ROAS, and CPA.",
#         #  "Generate a high-level ROAS plot of Campaign ID CMP_2025_2158 for brand Lifebuoy for jan 2025.", # provde the month range 
#         #  "Provide a trend analysis for CTR for Campaign ID CMP_2025_2158 (Lifebuoy), including a visualization to highlight performance trends for jan 2025.", # mention period range 
#         #  "Illustrate the conversion performance for Campaign ID CMP_2025_2158 (Lifebuoy) with a chart. for jan 2025.",
#         #  "Identify the best KPIs for evaluating the performance of Campaign ID CMP_2025_2158 (Lifebuoy) for jan 2025.",
#          "What are the core details for Campaign ID CMP_2025_0005 for the brand Kissan, including its name, category, and primary objective?",
#          "Who is the campaign manager and what are the specific sub-objectives for Campaign ID CMP_2025_0005 (Kissan)?"
#    ]

    flat_prompts = [
    prompt
    for section in question_list
    for prompt in section.get("prompts", [])
    ]
 
    final_results = []
    failed_prompts = []
    # with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    # # Submit tasks and store future objects
    #     futures = [executor.submit(agent_call,prompt, tool_context) for prompt in flat_prompts]

    # # Process results as they become available
    #     done, not_done = concurrent.futures.wait(
    #     futures, 
    #     timeout=None, 
    #     return_when=concurrent.futures.ALL_COMPLETED
    #     )

    #     for prompt,future in zip(flat_prompts,done):
    #         try:
    #             final_results.append({
    #             "prompt": prompt,
    #             "response": future.result()
    #         })
    #         except Exception as e:
    #              failed_prompts.append({
    #             "prompt": prompt,
    #             "error": str(e)
    #         })
        
    # question_list= [
    #                 "What customization and filtering options are available for analyzing the performance of Campaign ID: CMP_2025_0007 for Continental? Specifically, list available timelines (e.g., daily, weekly, monthly) and segmentation options (e.g., by creative, channel, audience)."]
    # print(f"prompt generator output: {str(question_list)}")
    
    tasks = [agent_call(prompt, tool_context) for prompt in flat_prompts]
    print('Parallel call start',time.localtime())
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print('Parallel call end',time.localtime())
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

    # Sequential flow 
    Sequential_Agent = SequentialAgent(
        name="Sequential_Agent",
        sub_agents=[campaign_analysis_root_agent,campaign_comparison_root_agent, executive_summary_root_agent, recommendation_root_agent],
        description="Executes a sequence of code writing, reviewing, and refactoring.", # add this as a wrapper in agent file 
    )
    
    agent_tool = AgentTool(agent=Sequential_Agent)

    Sequential_agent_output = await agent_tool.run_async(
         args= {'request':"\n".join(tool_context.state["db_ds_agent_output"])}, tool_context=tool_context
    )
    tool_context.state[" Sequential_agent_output"] =  Sequential_agent_output
    return "Executed Sucessfully"