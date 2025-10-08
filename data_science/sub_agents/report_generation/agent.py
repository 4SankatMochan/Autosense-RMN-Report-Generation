"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import SequentialAgent
from data_science.sub_agents.text_viz_json_agent.agent import root_agent as text_viz_json_agent
from data_science.sub_agents.report_summarizer.agent import root_agent as text_viz_report_summarizer_agent



root_agent = SequentialAgent(
    description= "Sequential Report Generation Agent",
    name="report_generation_agent",
    sub_agents = [text_viz_json_agent,text_viz_report_summarizer_agent]
    
)