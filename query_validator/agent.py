
from google.adk.agents import Agent
from google.genai import types
from .prompts import instructions
from .tools import  mark_clarification,set_perceived_query,approve_query,auto_approve_query
from io import BytesIO
from google.cloud import storage
import json
import os
 

from google.adk.agents.callback_context import CallbackContext
def setup_before_agent_call(callback_context: CallbackContext):
    ## File Reading
    bucket_name = os.getenv("BUCKET_NAME")
    persona = os.getenv('persona_file_path')
    persona_report = os.getenv('persona_report_map_path')
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    ########## Reading persona.json
    blob = bucket.blob(persona)
    persona = blob.download_as_text()
    person_json = json.loads(persona)
    callback_context.state['persona'] = person_json
    callback_context.state['kpis'] = person_json[0]['relevant_kpis']
    
agent_tools = [
    mark_clarification,
    set_perceived_query,
    approve_query,
    auto_approve_query
]

root_agent = Agent(
    name="query_validation_agent_v1",
    model="gemini-2.5-flash",
    description="Helps users refine and confirm their queries before execution.",
    instruction=instructions(),
    tools=agent_tools,
    generate_content_config=types.GenerateContentConfig(temperature=0.3),
    disallow_transfer_to_parent=True,
    before_agent_callback=setup_before_agent_call,
)

