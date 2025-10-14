"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import SequentialAgent
from report_generation.sub_agents.text_viz_json_agent.agent import root_agent as text_viz_json_agent
from report_generation.sub_agents.report_summarizer.agent import root_agent as text_viz_report_summarizer_agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
def setup_before_agent_call(callback_context: CallbackContext):
    callback_context.state["persona_context"] = """
"""
    # callback_context.state["session_id"] = callback_context._invocation_context.session.id
    print(f"inside report gen seq agent: session id from invocation context {callback_context._invocation_context.session.id}")
    callback_context.state["session_id"] = callback_context._invocation_context.session.id
    print(f"inside report gen seq agent: session id from state {callback_context.state["session_id"]}")

root_agent = SequentialAgent(
    description= "Sequential Report Generation Agent",
    name="report_generation_agent",
    sub_agents = [text_viz_json_agent,text_viz_report_summarizer_agent],
    before_agent_callback=setup_before_agent_call,
    
)