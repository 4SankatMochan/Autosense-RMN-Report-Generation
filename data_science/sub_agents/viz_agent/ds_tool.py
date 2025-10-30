from google.adk.tools import ToolContext
from ...sub_agents import ds_agent
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import Part, Blob
import os


async def call_ds_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data science (nl2py) agent."""

    if question == "N/A":
        return tool_context.state["db_agent_output"]

    input_data = tool_context.state["query_result"]

    output_file = f"VizChart.png"
    artifact_name = tool_context.state.get('artifact_name')
    folder_name = str(artifact_name).lower()
    image_path = f"{folder_name}_{output_file}"
    json_path = f"{folder_name}_data.json"
    question_with_data = f"""
  Question to answer: {question}

  Actual data to analyze prevoius quesiton is already in the following:
  {input_data}
  While saving image and chart metadata name of image must be {image_path} and name of chart metadata must be {json_path}
  """
    log_file_path = os.path.join(os.getcwd(), "debug_log.txt")
    with open(log_file_path, 'a') as f:
        f.write(f'call is from ds_tool. \n')

    agent_tool = AgentTool(agent=ds_agent)

    ds_agent_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )


    tool_context.state["ds_agent_output"] = ds_agent_output
    # Create plain text artifact
    text_artifact = Part(
        inline_data=Blob(
            mime_type="text/plain",
            data=str(ds_agent_output).encode("utf-8")
        )
    )
    # Name the artifact file
    artifact_name = tool_context.state.get('artifact_name')
    folder_name = str(artifact_name).lower()
    text_path = f"{folder_name}_viz_ds_agent.txt"
    # Save the artifact
    await tool_context.save_artifact(text_path, text_artifact)
    return ds_agent_output