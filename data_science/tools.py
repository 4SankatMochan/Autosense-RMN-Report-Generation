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

from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
from .sub_agents import db_agent, ds_agent, dv_agent
import base64
from google.genai.types import Part, Blob
import os
import json
from .logging.db_agent_call_logger import log_db_agent


from pydantic import BaseModel 
class ToolInput(BaseModel):
    request: str  

    class Config:
        extra = "ignore"

# import datetime
# import json
async def call_db_agent(
    question: str,
    tool_context: ToolContext,
    **kwargs
    
):
    """Tool to call database (nl2sql) agent."""
    print(
        "\n call_db_agent.use_database:"
        f' {tool_context.state["all_db_settings"]["use_database"]}'
    )
    log_file_path = os.path.join(os.getcwd(), "debug_log.txt")
    with open(log_file_path, 'a') as f:
        f.write(f"\n sesssion id from call_db_agent: {tool_context._invocation_context.session.id}\n")
        f.write(f"{tool_context.state.get('user_query')} \n")

    tool_context.state['session_id'] = tool_context._invocation_context.session.id

    agent_tool = AgentTool(agent=db_agent)
    ### Db_agent gets different question from
    # Validate and sanitize input
    validated_input = ToolInput(request=question)
    db_agent_output = await agent_tool.run_async(
        args={"request": validated_input.request}, tool_context=tool_context
    )
    tool_context.state["db_agent_output"] = db_agent_output
    # Create plain text artifact
    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=str(db_agent_output).encode("utf-8")
        )
    )
    # tool_context.state['user_query'] = question # Using user_query to name artifacts in GCS Bucket
    user_query = tool_context.state.get('user_query')
    folder_name = str(user_query).replace(" ", "_").lower()
    text_path = f"{folder_name}_db_agent.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)

    ###### logging #######
    log_db_agent(question, tool_context, db_agent_output)
    #####################    
    return db_agent_output


async def call_ds_agent(
    question: str,
    tool_context: ToolContext,
    **kwargs
    
):
    """Tool to call data science (nl2py) agent."""

    if question == "N/A":
        return tool_context.state["db_agent_output"]

    input_data = tool_context.state["query_result"]
    # tool_context.state['user_query'] = question   # Present in db_agent
    question_with_data = f"""
  Question to answer: {question}

  Actual data to analyze prevoius quesiton is already in the following:
  {input_data}

  """
    log_file_path = os.path.join(os.getcwd(), "debug_log.txt")
    with open(log_file_path, 'a') as f:
        f.write(f'ds_agent from root. \n')

    agent_tool = AgentTool(agent=ds_agent)
    validated_input = ToolInput(request=question)
    ds_agent_output = await agent_tool.run_async(
        args={"request": validated_input.request}, tool_context=tool_context
    )

    tool_context.state["ds_agent_output"] = ds_agent_output

        # Create plain text artifact
    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=str(ds_agent_output).encode("utf-8")
        )
    )
    user_query = tool_context.state.get('user_query')
    folder_name = str(user_query).replace(" ", "_").lower()
    text_path = f"{folder_name}_ds_agent.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)
    return ds_agent_output

async def call_viz_agent(
    question: str,
    tool_context: ToolContext,
    **kwargs
    
):
    """Tool to call data visualization agent (supports LLM or direct chart outputs)."""

    if question == "N/A":
        return tool_context.state.get("db_agent_output")

    input_data = tool_context.state.get("query_result")
    columns = list(input_data[0].keys())
    tool_context.state['query_columns'] = columns
    # tool_context.state['user_query'] = question #cmntd by krishna on 26-sept
    # User query under db_agent and viz_agent are different. Mostly user quries under viz_agent is
    # similar to user input. 
    question_with_data = f"""
    Question to answer: {question}

    Actual data to analyze for the previous question is already in the following:
    {input_data}
    """
    log_file_path = os.path.join(os.getcwd(), "debug_log.txt")
    with open(log_file_path, 'a') as f:
        f.write(f'question with data is >>>>>>>:{question_with_data}\n')
        f.write(f"sesssion id from call_viz_agent: {tool_context._invocation_context.session.id}\n")

    agent_tool = AgentTool(agent=dv_agent)
    validated_input = ToolInput(request=question)
    dv_agent_output = await agent_tool.run_async(
        args={"request": validated_input.request}, tool_context=tool_context)
    tool_context.state["dv_agent_output"] = dv_agent_output

    # Create plain text artifact
    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=str(dv_agent_output).encode("utf-8")
        )
    )
    # Name the artifact file
    user_query = tool_context.state.get('user_query')
    folder_name = str(user_query).replace(" ", "_").lower()
    text_path = f"{folder_name}_viz_agent.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)



    text_parts = []
    image_parts = []

    # --- Case 1: Generative AI response ---
    if hasattr(dv_agent_output, "candidates"):
        for part in dv_agent_output.candidates[0].content.parts:
            if hasattr(part, "text"):
                text_parts.append(part.text)
            elif hasattr(part, "inline_data"):
                image_parts.append({
                    "mime_type": part.inline_data.mime_type,
                    "data": part.inline_data.data  # raw bytes
                })

    # --- Case 2: Dict from chart_plotting_tool ---
    elif isinstance(dv_agent_output, dict):
        if "text" in dv_agent_output:
            text_parts.append(str(dv_agent_output["text"]))

        if "artifact" in dv_agent_output and "image" in dv_agent_output:
            base64_src = dv_agent_output["image"].get("src", "")
            if base64_src.startswith("data:image"):
                # Strip "data:image/png;base64," prefix
                base64_data = base64_src.split(",")[1] if "," in base64_src else base64_src
                image_bytes = base64.b64decode(base64_data)

                image_parts.append({
                    "mime_type": dv_agent_output["artifact"].get("type", "image/png"),
                    "data": image_bytes
                })

                # Also wrap into a Part/Blob for consistency
                image_blob = Part(
                    inline_data=Blob(
                        data=image_bytes,
                        mime_type=dv_agent_output["artifact"].get("type", "image/png")
                    )
                )

                # Save as artifact in ADK context
                await tool_context.save_artifact(
                    dv_agent_output["artifact"]["name"],
                    image_blob
                )

    # --- Case 3: Plain string output ---
    elif isinstance(dv_agent_output, str):
        text_parts.append(dv_agent_output)

    else:
        text_parts.append(str(dv_agent_output))

    return {
        "text": "\n".join(filter(None, text_parts)),
        "images": image_parts
    }