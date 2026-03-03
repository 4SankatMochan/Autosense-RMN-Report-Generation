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
    # print("inside prompt executor agent")
    # print(f"session id inside call_db_ds_agent tool inside prompt_executor: {tool_context._invocation_context.session.id}")
    question_list = tool_context.state.get("prompt_generator_out")
    # flat_prompts = [
    #     prompt
    #     for section in question_list
    #     for prompt in section.get("prompts", [])
    # ]
 
    # question_list= [
    #                 "What customization and filtering options are available for analyzing the performance of Campaign ID: CMP_2025_0007 for Continental? Specifically, list available timelines (e.g., daily, weekly, monthly) and segmentation options (e.g., by creative, channel, audience)."]
    # print(f"prompt generator output: {str(question_list)}")
    tasks = [agent_call(prompt, tool_context) for prompt in question_list]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    final_results = []
    failed_prompts = []

    for prompt, result in zip(question_list, results):
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
    
    # # return "Executed Successfully"
    # tool_context.state["db_ds_agent_output"] = results  
    
    # Sequential flow 
    Sequential_Agent = SequentialAgent(
        name="Sequential_Agent",
        sub_agents=[campaign_analysis_root_agent,campaign_comparison_root_agent, executive_summary_root_agent, recommendation_root_agent],
        description="Executes a sequence of code writing, reviewing, and refactoring.", # add this as a wrapper in agent file 
    )# add agent as a tool in agent.py
    
    agent_tool = AgentTool(agent=Sequential_Agent)

    print(type(tool_context.state["db_ds_agent_output"]))
    print(tool_context.state["db_ds_agent_output"])
    Sequential_agent_output = await agent_tool.run_async(
         args= {'request':"\n".join(tool_context.state["db_ds_agent_output"])}, tool_context=tool_context
    )
    tool_context.state["sequential_agent_output"] =  Sequential_agent_output
    return "Executed Successfully"