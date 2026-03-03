import os
from google.genai import types
from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from .subagents.prompt_generator_list.agent import root_agent as prompt_generator
from .subagents.prompt_executor.agent import root_agent as prompt_executor
from data_science.agent import root_agent as db_ds_multiagent
from .subagents.report_generation.agent import root_agent as report_generator
from .prompts import return_instructions_root
from io import BytesIO
from google.cloud import storage

import pandas as pd
import json
import sys
def excel_to_json(df):
    # df = pd.read_excel(excel_path)
    grouped = {}

    for _, row in df.iterrows():
        persona = row["persona"]
        objective = row["objective"]
        if persona not in grouped:
            grouped[persona] = {"report_type": row["report_type"], "objectives": {}}

        grouped[persona]["objectives"][objective] = {
            "sample_kpis": str(row["sample_kpis"]).split(","),
            "focus_kpis": str(row["focus_kpis"]).split(","),
            "supporting_kpis": str(row["supporting_kpis"]).split(","),
            "data_granularity": row["data_granularity"],
            "filters": str(row["filters"]).split(","),
            "attribution_window": row["attribution_window"],
            "visualization_pref": str(row["visualization_pref"]).split(","),
            "output_pref": str(row["output_pref"]).split(","),
            "interaction_pref": str(row["interaction_pref"]).split(","),
            "benchmarking_ctx": str(row["benchmarking_ctx"]).split(","),
            "actionability_level": row["actionability_level"],
            "integration_needs": str(row["integration_needs"]).split(","),
            "confidence_threshold": row["confidence_threshold"],
            "answer_boundaries": [row["answer_boundaries"]],
            "fallback_behavior": row["fallback_behavior"],
            "data_freshness_validity": row["data_freshness_validity"],
            "explainability_tag": row["explainability_tag"],
            "name_of_report": row["name_of_report"],
            "tone": str(row["tone"]).split(","),
            "narrative_focus": [row["narrative_focus"]],
            "recommendation_framework": [{"logic": logic.strip()} for logic in str(row["recommendation_framework"]).split(";")]
        }
    # return json.dumps(grouped, indent=2)
    return grouped

def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""
    ## File Reading
    bucket_name = os.getenv("BUCKET_NAME")
    persona = os.getenv('persona_file_path')
    persona_report = os.getenv('persona_report_map_path')
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    ########## Reading persona.json
    blob = bucket.blob(persona)
    persona = blob.download_as_text()
    callback_context.state['persona'] = persona

    ######## Adding report_context (Madhuresh work)
    # client = storage.Client()
    # bucket = client.bucket(bucket_name)
    # Get the blob (file object)
    blob = bucket.blob(persona_report)
    # Download the file content as bytes
    excel_bytes = blob.download_as_bytes()
    # Read it into a pandas DataFrame
    df = pd.read_excel(BytesIO(excel_bytes), engine='openpyxl')
    persona_report_context = excel_to_json(df)
    callback_context.state['persona_report'] = persona_report_context
    log_file_path = os.path.join(os.getcwd(), "debug_log.txt")
    with open(log_file_path, 'a') as f:
        # f.write(f"CallbackContext attributes:, {dir(callback_context)}\n")
        f.write(f"root folder")
        f.write(f"{callback_context.user_content}\n")
        f.write(f"{callback_context.user_content.parts[0].text}")
        # f.write(f"persona is {persona}\n")
        # f.write(f'persona_report {pd.read_excel(BytesIO(persona_report))}\n')
#     callback_context.state["report_template"] = """Use any template matching the content
# """
#     callback_context.state["persona_context"] = """
# """
    user_message = callback_context.user_content.parts[0]
    if user_message.text:
        original_prompt = user_message.text
        callback_context.state['user_query'] = original_prompt
    
root_agent = SequentialAgent(
    name="Coordinator",
    # model=os.getenv("ROOT_AGENT_MODEL"),
    # description=return_instructions_root(),
    sub_agents=[ 
        # db_ds_multiagent,
        prompt_generator,
        prompt_executor,
        report_generator
    ],
    before_agent_callback=setup_before_agent_call,
    # disallow_transfer_to_parent = True
)