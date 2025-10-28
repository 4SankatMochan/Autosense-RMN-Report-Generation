import os
from google.genai import types
from google.adk.agents import Agent, LlmAgent
from google.adk.agents.callback_context import CallbackContext
from prompt_executor.agent import root_agent as prompt_executor
from data_science.agent import root_agent as data_science
from prompt_generator_list.agent import root_agent as prompt_generator
from report_generation.agent import root_agent as report_generator
from .prompts import return_instructions_root
from io import BytesIO
from google.cloud import storage

# import pandas as pd
# import json
# import sys
# def excel_to_json(df):
#     # df = pd.read_excel(excel_path)
#     grouped = {}

#     for _, row in df.iterrows():
#         persona = row["persona"]
#         objective = row["objective"]
#         if persona not in grouped:
#             grouped[persona] = {"report_type": row["report_type"], "objectives": {}}

#         grouped[persona]["objectives"][objective] = {
#             "sample_kpis": str(row["sample_kpis"]).split(","),
#             "focus_kpis": str(row["focus_kpis"]).split(","),
#             "supporting_kpis": str(row["supporting_kpis"]).split(","),
#             "data_granularity": row["data_granularity"],
#             "filters": str(row["filters"]).split(","),
#             "attribution_window": row["attribution_window"],
#             "visualization_pref": str(row["visualization_pref"]).split(","),
#             "output_pref": str(row["output_pref"]).split(","),
#             "interaction_pref": str(row["interaction_pref"]).split(","),
#             "benchmarking_ctx": str(row["benchmarking_ctx"]).split(","),
#             "actionability_level": row["actionability_level"],
#             "integration_needs": str(row["integration_needs"]).split(","),
#             "confidence_threshold": row["confidence_threshold"],
#             "answer_boundaries": [row["answer_boundaries"]],
#             "fallback_behavior": row["fallback_behavior"],
#             "data_freshness_validity": row["data_freshness_validity"],
#             "explainability_tag": row["explainability_tag"],
#             "name_of_report": row["name_of_report"],
#             "tone": str(row["tone"]).split(","),
#             "narrative_focus": [row["narrative_focus"]],
#             "recommendation_framework": [{"logic": logic.strip()} for logic in str(row["recommendation_framework"]).split(";")]
#         }
#     return json.dumps(grouped, indent=2)
def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""
    callback_context.state["report_template"] = """Use any template matching the content
"""
    callback_context.state["persona_context"] = """
"""
    



root_agent = LlmAgent(
    name="Coordinator",
    model=os.getenv("ROOT_AGENT_MODEL"),
    description=return_instructions_root(),
    sub_agents=[ 
        data_science,
        prompt_executor,
        prompt_generator, 
        report_generator
    ],
    before_agent_callback=setup_before_agent_call,
    disallow_transfer_to_parent= True
)