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

import datetime
import json

async def call_db_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call database (nl2sql) agent."""
    print(
        "\n call_db_agent.use_database:"
        f' {tool_context.state["all_db_settings"]["use_database"]}'
    )

    agent_tool = AgentTool(agent=db_agent)
 
 
    db_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )
    tool_context.state["db_agent_output"] = db_agent_output
    ###### logging #######    
    # Generate log file name with datetime
    # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    log_file = f"debug_log_db_agent_{timestamp}.txt"
    # log_file = "debug_log_db_agent.txt"

    with open(log_file, "a") as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write(f"question: {question}\n")
        f.write("----" * 10 + "\n")
        # Write only if key exists in tool_context.state
        for key, label in [
            ("tool_called", "tool_called"),
            ("config_used", "config_used"),
            ("sql_query", "sql_query"),
            ("SQL Method DC/QP", "SQL Method DC/QP"),
            ("sql_query_before_transpile", "sql_query_before_transpile"),
            ("sql_query_after_transpile", "sql_query_after_transpile"),
        ]:
            value = tool_context.state.get(key)
            if value is not None:
                f.write(f"{label}: {value}\n")
                f.write("----" * 10 + "\n")
            else:
                f.write("\n")  # leave line empty
                f.write("----" * 10 + "\n")

        # # Print dict values one by one
        # f.write("db_agent_output:\n")
        # if isinstance(db_agent_output, dict):
        #     for k, v in db_agent_output.items():
        #         f.write(f"  {k}: {v}\n")
        #         f.write("----" * 10 + "\n")
        # else:
        #     f.write(f"  {db_agent_output}\n")
        #     f.write("----" * 10 + "\n")
        # Pretty-print JSON dict
        f.write("db_agent_output:\n")
        try:
            f.write(json.dumps(db_agent_output, indent=4, ensure_ascii=False)+ "\n")
        except Exception:
            f.write(str(db_agent_output)+ "\n")  # fallback if not serializable

        f.write("====" * 100 + "\n")

    #############
    return db_agent_output


async def call_ds_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data science (nl2py) agent."""

    if question == "N/A":
        return tool_context.state["db_agent_output"]

    input_data = tool_context.state["query_result"]

    question_with_data = f"""
  Question to answer: {question}

  Actual data to analyze prevoius quesiton is already in the following:
  {input_data}

  """

    agent_tool = AgentTool(agent=ds_agent)

    ds_agent_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )
    tool_context.state["ds_agent_output"] = ds_agent_output
    return ds_agent_output

async def call_viz_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data visualization agent (supports LLM or direct chart outputs)."""

    if question == "N/A":
        return tool_context.state.get("db_agent_output")

    input_data = tool_context.state.get("query_result")

    question_with_data = f"""
    Question to answer: {question}

    Actual data to analyze for the previous question is already in the following:
    {input_data}
    """
    print(f'question with data is >>>>>>>:{question_with_data}')

    agent_tool = AgentTool(agent=dv_agent)
    dv_agent_output = await agent_tool.run_async(
        args={"request": question_with_data},
        tool_context=tool_context,
    )

    tool_context.state["dv_agent_output"] = dv_agent_output

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