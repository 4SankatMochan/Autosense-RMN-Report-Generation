# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Top level agent for data agent multi-agents.

-- it get data from database (e.g., BQ) using NL2SQL
-- then, it use NL2Py to do further data analysis as needed
"""
import os
from datetime import date

from google.genai import types
from google.genai.types import  Content, Part
from google.adk.events import Event, EventActions
# from google.generativeai.types import Event, Content, Part
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import load_artifacts

from .sub_agents import bqml_agent
# from .sub_agents import report_generation_agent
from .sub_agents.bigquery.tools import (
    get_database_settings as get_bq_database_settings,
)
from .prompts import return_instructions_root
from .tools import call_db_agent, call_viz_agent, call_ds_agent
import logging
import concurrent.futures
from google.cloud import storage
from io import BytesIO
import re
from root.subagents.gcs_cache import get_cached

#from .sub_agents.nl2sql.agent import nl2sql_agent
#from .sub_agents.descriptive_analysis.agent import descriptive_analysis_agent
#from .sub_agents.descriptive_summary.agent import descriptive_summary_agent
#from .sub_agents.delivery.agent import delivery_agent
date_today = date.today()
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
    #return json.dumps(grouped, indent=2)
    return grouped

async def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent — parallel GCS reads with module-level TTL cache."""
    bucket_name = os.getenv("BUCKET_NAME")
    persona_path = os.getenv('persona_file_path')
    persona_report_path = os.getenv('persona_report_map_path')
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Download persona.json and persona_report.xlsx in parallel threads.
    # get_cached avoids re-downloading within CACHE_TTL (1 h).
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_persona = pool.submit(
            get_cached, bucket.blob(persona_path),
            lambda b: b.download_as_text()
        )
        f_report = pool.submit(
            get_cached, bucket.blob(persona_report_path),
            lambda b: b.download_as_bytes()
        )
        persona_text = f_persona.result()
        excel_bytes  = f_report.result()

    callback_context.state['persona'] = persona_text

    df = pd.read_excel(BytesIO(excel_bytes), engine='openpyxl')
    callback_context.state['persona_report'] = excel_to_json(df)
    prmpt = callback_context.user_content.parts[0].text
    prmpt = prmpt.replace("\n", " ")
    prmpt = re.sub(r"\s+", "_", prmpt.strip())
    # Remove characters that are invalid in Windows file/folder names
    prmpt = re.sub(r'[<>:"/\\|?*]', '', prmpt)
    prmpt = re.match(r'^.{0,150}', prmpt)  # keep well under MAX_PATH
    artifact_name = prmpt.group()
    user_message = callback_context.user_content.parts[0]
    if user_message.text:
        original_prompt = user_message.text
        callback_context.state['user_query'] = original_prompt
        callback_context.state['artifact_name'] = artifact_name
    

    # setting up database settings in session.state
    if "database_settings" not in callback_context.state:
        db_settings = dict()
        db_settings["use_database"] = "BigQuery"
        callback_context.state["all_db_settings"] = db_settings

    # setting up schema in instruction
    if callback_context.state["all_db_settings"]["use_database"] == "BigQuery":
        callback_context.state["database_settings"] = await get_bq_database_settings()
        schema = callback_context.state["database_settings"]["bq_ddl_schema"]

        callback_context._invocation_context.agent.instruction = (
            return_instructions_root()
            + f"""

    --------- The BigQuery schema of the relevant data with a few sample rows. ---------
    {schema}

    """
        )


root_agent = Agent(
    model=os.getenv("ROOT_AGENT_MODEL"),
    name="db_ds_multiagent",
    instruction=return_instructions_root(),
    global_instruction=(
        f"""
        You are a Data Science and Data Analytics Multi Agent System.
        Todays date: {date_today}
        """
    ),
    sub_agents=[bqml_agent],
    tools=[
        call_db_agent,
        call_viz_agent, 
        call_ds_agent,
        load_artifacts,
    ],
    before_agent_callback=setup_before_agent_call,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
