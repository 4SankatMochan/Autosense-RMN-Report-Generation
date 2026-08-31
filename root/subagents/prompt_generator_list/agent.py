
# """Agent to call db_ds_agent parallely.
# """
# import os
# from datetime import date

# from google.genai import types

# from google.adk.agents import Agent
# from google.adk.agents.callback_context import CallbackContext
# from google.adk.tools import load_artifacts

# from .prompts import return_instructions_root
# from .tools import generate_prompt
# date_today = date.today()

# root_agent = Agent(
#     model=os.getenv("ROOT_AGENT_MODEL"),
#     name="prompt_generator",
#     instruction=return_instructions_root(),
#     tools=[
#         generate_prompt,
#     ],
#     generate_content_config=types.GenerateContentConfig(temperature=0.01),
# )
############# NEW ###############

"""Agent to generate contextual prompts for report creation using persona and persona_report context."""
import os
from datetime import date
from google.genai import types
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from .prompts import return_instructions_root
from .tools import generate_prompt
from io import BytesIO
from google.cloud import storage
import concurrent.futures
import pandas as pd
import time
import json
from root.subagents.gcs_cache import get_cached

date_today = date.today()

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
    """Setup the agent — parallel GCS reads with module-level TTL cache."""
    print('Prompt generation start', time.strftime('%H:%M:%S'))
    bucket_name = os.getenv("BUCKET_NAME")
    persona_path = os.getenv('persona_file_path')
    persona_report_path = os.getenv('persona_report_map_path')
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Download both files in parallel; get_cached avoids re-downloading
    # within CACHE_TTL (1 h) — eliminates sequential GCS round-trips.
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

    persona = json.loads(persona_text)
    print(f"Persona loaded into context: {type(persona)}")
    callback_context.state['persona'] = persona

    df = pd.read_excel(BytesIO(excel_bytes), engine='openpyxl')
    callback_context.state['persona_report'] = excel_to_json(df)
    uc = getattr(callback_context, 'user_content', None)
    if uc and getattr(uc, 'parts', None):
        user_message = uc.parts[0]
        if getattr(user_message, 'text', None):
            print(f"Original user query: {user_message.text}")
            callback_context.state['user_query'] = user_message.text

import logging
from functools import wraps
import inspect

_pg_logger = logging.getLogger(__name__)


def stage1_after_agent_call(callback_context: CallbackContext):
    """Stamp Stage 1 (prompt generation) end time into session state."""
    t = time.perf_counter()
    callback_context.state['stage1_end_perf'] = t
    start = callback_context.state.get('pipeline_start_perf', t)
    _pg_logger.info("Stage 1 — Prompt Generation done in %.1f s", t - start)

from pydantic import BaseModel
from typing import List

class Section(BaseModel):
    section_name: str
    prompts: List[str]

class PromptListOutput(BaseModel):
    prompt_list: List[Section]

# ✅ Root Agent for Prompt Generator
root_agent = Agent(
    model=os.getenv("ROOT_AGENT_MODEL"),
    name="prompt_generator",
    instruction=return_instructions_root(),
    tools=[generate_prompt],
    before_agent_callback=setup_before_agent_call,
    after_agent_callback=stage1_after_agent_call,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
