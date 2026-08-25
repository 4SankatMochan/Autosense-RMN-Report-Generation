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
import datetime
import asyncio

from pydantic import BaseModel 
class ToolInput(BaseModel):
    request: str  

    class Config:
        extra = "ignore"

# import datetime
# import json

# Visualization intent keywords. If a db prompt contains any of these, we deterministically
# build a chart from the fetched data (no LLM decision involved).
_VIZ_KEYWORDS = (
    "plot", "chart", "graph", "trend", "visuali", "over time",
    "comparison", "compare", "distribution",
)


async def _maybe_build_deterministic_chart(question, tool_context, folder_name):
    """Deterministically build & save a chart from ``query_result`` for visualization prompts.

    The chart is saved as ``<folder_name>_VizChart.png`` (+ ``<folder_name>_data.json``) — the exact
    names the report's ``text_viz_json`` step already harvests — so charts reach the PDF WITHOUT
    depending on the LLM router calling the viz agent. Best-effort: never raises.
    """
    tag = "[deterministic-chart]"
    try:
        rows = tool_context.state.get("query_result")
        if isinstance(rows, str):
            try:
                rows = json.loads(rows)
            except Exception:
                rows = None
        n = len(rows) if isinstance(rows, list) else 0
        print(f"{tag} prompt={str(folder_name)[:60]!r} rows={n}")
        if not rows or not isinstance(rows, list) or not isinstance(rows[0], dict) or n < 2:
            print(f"{tag} skip: no usable multi-row tabular data (rows={n})")
            return

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
        import io

        df = pd.DataFrame(rows)
        if df.empty or df.shape[1] < 2:
            print(f"{tag} skip: df shape {df.shape}")
            return

        # Identify a date/time-like x column
        date_col = None
        for c in df.columns:
            cl = str(c).lower()
            if any(k in cl for k in ("date", "day", "week", "month", "time")):
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().sum() >= max(2, int(len(df) * 0.5)):
                    df[c] = parsed
                    date_col = c
                    break

        # Numeric columns (coerce where possible)
        numeric_cols = []
        for c in df.columns:
            if c == date_col:
                continue
            coerced = pd.to_numeric(df[c], errors="coerce")
            if coerced.notna().sum() >= max(1, int(len(df) * 0.5)):
                df[c] = coerced
                numeric_cols.append(c)
        if not numeric_cols:
            print(f"{tag} skip: no numeric columns among {list(df.columns)}")
            return

        plt.figure(figsize=(10, 5))
        title = (question or "Chart").strip()
        if len(title) > 90:
            title = title[:90] + "..."

        if date_col is not None:
            d = df.sort_values(date_col)
            for c in numeric_cols[:4]:
                plt.plot(d[date_col], d[c], marker="o", label=str(c))
            plt.xlabel(str(date_col))
            plt.xticks(rotation=45)
            plt.legend()
            chart_type = "line"
        else:
            cat_cols = [c for c in df.columns if c not in numeric_cols]
            if not cat_cols:
                print(f"{tag} skip: no categorical column for bar chart")
                plt.close("all")
                return
            x, y = cat_cols[0], numeric_cols[0]
            plt.bar(df[x].astype(str), df[y])
            plt.xlabel(str(x))
            plt.ylabel(str(y))
            plt.xticks(rotation=45)
            chart_type = "bar"

        plt.title(title, fontsize=11)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120)
        plt.close("all")
        buf.seek(0)
        image_bytes = buf.read()

        image_artifact = Part(inline_data=Blob(data=image_bytes, mime_type="image/png"))
        meta = {
            "title": title,
            "chart_type": chart_type,
            "x": str(date_col) if date_col is not None else None,
            "series": [str(c) for c in numeric_cols[:4]],
        }
        json_artifact = Part(
            inline_data=Blob(mime_type="text/plain", data=json.dumps(meta).encode("utf-8"))
        )
        await tool_context.save_artifact(f"{folder_name}_VizChart.png", image_artifact)
        await tool_context.save_artifact(f"{folder_name}_data.json", json_artifact)
        print(f"{tag} SAVED {str(folder_name)[:50]}_VizChart.png ({chart_type}, series={[str(c) for c in numeric_cols[:4]]})")
    except Exception as e:
        import traceback
        print(f"[deterministic-chart] ERROR ({type(e).__name__}): {e}")
        traceback.print_exc()


async def call_db_agent(
    question: str,
    tool_context: ToolContext,
    **kwargs

):
    """Tool to call database (nl2sql) agent."""
    print(f"db: at time: {datetime.datetime.now().strftime("%H:%M:%S")} called que: {question}")
    print(f"sesssion id from call_db_agent: {tool_context._invocation_context.session.id}\n")
    # print(
    #     "\n call_db_agent.use_database:"
    #     f' {tool_context.state["all_db_settings"]["use_database"]}'
    # )
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
    artifact_name = tool_context.state.get('artifact_name')
    folder_name = str(artifact_name).lower()
    text_path = f"{folder_name}_db_agent.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)

    # Deterministically produce a chart for visualization prompts (does not rely on the LLM
    # router choosing call_viz_agent). Saved as <folder_name>_VizChart.png for the report.
    await _maybe_build_deterministic_chart(question, tool_context, folder_name)

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
    print(f"ds: at time: {datetime.datetime.now().strftime("%H:%M:%S")} called que: {question}")
    if question == "N/A":
        return tool_context.state["db_agent_output"]

    input_data = tool_context.state["query_result"]
    # tool_context.state['user_query'] = question   # Present in db_agent
    question_with_data = f"""
  Question to answer: {question}

  Actual data to analyze previous question is already in the following:
  {input_data}

  """
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
    artifact_name = tool_context.state.get('artifact_name')
    folder_name = str(artifact_name).lower()
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
    print(f" viz:at time: {datetime.datetime.now().strftime("%H:%M:%S")} called que: {question}")
    print(f"sesssion id from call_viz_agent: {tool_context._invocation_context.session.id}\n")
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
    artifact_name = tool_context.state.get('artifact_name')
    folder_name = str(artifact_name).lower()
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