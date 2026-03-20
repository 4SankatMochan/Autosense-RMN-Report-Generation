from data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio
from .subagents.Campaign_analysis.agent import campaign_analysis_root_agent # try another way, might be issue 
from .subagents.Campaign_comparison.agent import campaign_comparison_root_agent
from .subagents.Executive_summary.agent import executive_summary_root_agent
from .subagents.Recommendation.agent import recommendation_root_agent
from google.adk.agents.sequential_agent import SequentialAgent

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
    # question_list = tool_context.state.get("prompt_generator_out")
    question_list = [
        {
        "section_name": "Context",
        "prompts": [
            "For Campaign ID CMP_2025_0001 by Dove, please provide the Campaign Name, Brand Name, Category, Media Types, Channel, Objective, Sub-Objective, Campaign Manager, Campaign Duration, Planned Budget, and Actual Spend."
        ]
        },
        {
        "section_name": "Campaign Overview",
        "prompts": [
            "Generate a high-level summary table for Campaign ID CMP_2025_0001 by Dove, including Campaign ID, Campaign Name, Budget (Planned Spend), Campaign Objective, Total Ad Spend, and Budget Utilization.",
            "If the objective for Campaign ID CMP_2025_0001 by Dove is 'Awareness', provide a metrics table including Channel, Total Ad Spend, Impressions, Unique Reach, Frequency, ROAS, and CPM.",
            "If the objective for Campaign ID CMP_2025_0001 by Dove is 'Consideration', provide a metrics table including Channel, Total Ad Spend, Impressions, Unique Reach, Clicks, CTR, CPC, CPCV, Viewed Units, Clicked Units, and Add To Cart.",
            "If the objective for Campaign ID CMP_2025_0001 by Dove is 'Conversion', provide a metrics table including Channel, Total Ad Spend, Impressions, Clicks, CTR, CVR, Viewed Transactions, Clicked Transactions, Viewed Revenue, Clicked Revenue, Total Campaign Revenue, ROAS, Incremental Sales Lift, and Conversions.",
            "If the objective for Campaign ID CMP_2025_0001 by Dove is 'Retention', provide a metrics table including Channel, Total Ad Spend, Conversions, CVR, Transactions Repeat, Units Sold, Total Campaign Revenue, Incremental Sales Lift, and ROAS."
        ]
        },
        {
        "section_name": "Campaign-wise Analysis",
        "prompts": [
            "Analyze the Return on Ad Spend (ROAS) for Campaign ID CMP_2025_0001 by Dove on a monthly basis. Include trends over time and across different channels, and suggest appropriate visualizations like charts or graphs.",
            "Provide a detailed analysis of the Click-Through Rate (CTR) for Campaign ID CMP_2025_0001 by Dove, broken down monthly. Illustrate performance trends over time, across channels, or by audience segments with suitable charts or graphs.",
            "Examine the Conversions for Campaign ID CMP_2025_0001 by Dove, presenting monthly performance. Include trends over time, across channels, or by audience segments, and recommend appropriate visualizations."
        ]
        }
    ]

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

    # Sequential flow 
    Sequential_Agent = SequentialAgent(
        name="Sequential_Agent",
        sub_agents=[campaign_analysis_root_agent,campaign_comparison_root_agent, executive_summary_root_agent, recommendation_root_agent],
        description="Executes a sequence of code writing, reviewing, and refactoring.", # add this as a wrapper in agent file 
    )
    
    agent_tool = AgentTool(agent=Sequential_Agent)

    Sequential_agent_output = await agent_tool.run_async(
         args= {'request':"\n".join(tool_context.state["db_ds_agent_output"])}
    )
    tool_context.state[" Sequential_agent_output"] =  Sequential_agent_output
    return "Executed Sucessfully"