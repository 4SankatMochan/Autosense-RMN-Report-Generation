# from .agent import campaign_analysis_root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import json
from google.cloud import storage
import base64
import re
from collections import defaultdict
from typing import List, Optional
import os
from vertexai.preview.generative_models import GenerativeModel

# async def camp_analysis(tool_context: Optional[ToolContext] = None, **kwargs):
#     # print(tool_context.state)
#     session_id = tool_context.state.get("session_id")
#     # print(f"session id inside text_viz_json: {session_id}")
#     bucket_name = os.getenv("BUCKET_NAME")
#     # session_prefix = f'data_science/user/{session_id}/'
#     session_prefix = f'prompt_executor/user/{session_id}/'
#     # session_prefix = f'default-app-name/user/{session_id}/'

#     # Initialize client
#     client = storage.Client()
#     bucket = client.bucket(bucket_name)

#     # Step 1: List and sort all blobs
#     blobs = list(bucket.list_blobs(prefix=session_prefix))
#     # Filter out unwanted blobs before sorting
#     filtered_blobs = [blob for blob in blobs if 'code_execution_image_' not in blob.name]
#     sorted_blobs = sorted(filtered_blobs, key=lambda b: b.updated)

#     # Step 2: Group blobs by base path (without /N), keep highest version
#     blob_versions = defaultdict(list)
#     versioned_blob_pattern = re.compile(r'(.+?)(?:/(\d+))$')  # Extract base path and version number

#     for blob in sorted_blobs:
#         match = versioned_blob_pattern.match(blob.name)
#         if match:
#             base_path = match.group(1)
#             version = int(match.group(2))
#             blob_versions[base_path].append((version, blob))

#     # Step 3: Select highest version for each base path
#     latest_blobs = {}
#     for base_path, versions in blob_versions.items():
#         # Pick the blob with max version number
#         latest_blob = max(versions, key=lambda x: x[0])[1]
#         latest_blobs[base_path] = latest_blob

#     # Step 4: Identify prompts from .json and .png files
#     prompt_map = defaultdict(dict)
#     for base_path, blob in latest_blobs.items():
#         filename = base_path.split('/')[-1]
#         if filename.endswith('_data.json'):
#             prompt = filename.replace('_data.json', '')
#             prompt_map[prompt]['json_blob'] = blob
#         elif filename.endswith('_VizChart.png'):
#             prompt = filename.replace('_VizChart.png', '')
#             prompt_map[prompt]['chart_blob'] = blob
#         elif filename.endswith('_viz_ds_agent.txt'):
#             prompt = filename.replace('_viz_ds_agent.txt', '')
#             prompt_map[prompt]['viz_ds_text'] = blob
#         elif filename.endswith('_viz_agent.txt'):
#             prompt = filename.replace('_viz_agent.txt', '')
#             prompt_map[prompt]['viz_text'] = blob
#         elif filename.endswith('_db_agent.txt'):
#             prompt = filename.replace('_db_agent.txt', '')
#             prompt_map[prompt]['db_text'] = blob
#         elif filename.endswith('_ds_agent.txt'):
#             prompt = filename.replace('_ds_agent.txt', '')
#             prompt_map[prompt]['ds_text'] = blob

#     # Step 5: Build result_data
#     result_data = {}
#     for idx, (prompt, blobs_dict) in enumerate(prompt_map.items(), start=1):
#         json_blob = blobs_dict.get('json_blob')
#         chart_blob = blobs_dict.get('chart_blob')
#         # viz_ds_blob = blobs_dict.get('viz_ds_text')
#         viz_blob = blobs_dict.get('viz_text')
#         db_blob =  blobs_dict.get('db_text')
#         ds_blob =  blobs_dict.get('ds_text')

#         result_data[f'prompt{idx}'] = {
#             'prompt': prompt.replace("_"," "),
#             'chart_url': None,
#             'json_data': None,
#             'viz_text': None,
#             # 'viz_ds_text': None,
#             'db_text': None,
#             'ds_text': None
#         }

#         # Download chart if present
#         if chart_blob:              # If chart is availabe
#             result_data[f'prompt{idx}']['chart_url'] = f'gs://{bucket_name}/{chart_blob.name}'
#             # Download JSON if present
#             if json_blob:
#                 result_data[f'prompt{idx}']['json_data'] = f'gs://{bucket_name}/{json_blob.name}'
#                 # Download viz agent text if present
#             if viz_blob:
#                 viz_string = viz_blob.download_as_text()
#                 result_data[f'prompt{idx}']['viz_text'] = viz_string
#             ## Need Alignment: Do we need to add db_text and ds_text as well in chart
#         elif ds_blob:
#             ds_string = ds_blob.download_as_text()
#             result_data[f'prompt{idx}']['ds_text'] = ds_string


#         elif db_blob:
#             db_string = db_blob.download_as_text()
#             try:
#               # Remove markdown formatting lines if present
#               if db_string.startswith("```json"):
#                   db_string = db_string.split("\n", 1)[1]  # Remove first line
#               if db_string.endswith("```"):
#                   db_string = db_string.rsplit("\n", 1)[0]  # Remove last line

#               # Now parse the cleaned JSON string
#               data = json.loads(db_string)

#               # Extract channel names from `nl_results`
#               nl_text = data["nl_results"]
#               result_data[f'prompt{idx}']['db_text'] = nl_text
#             except:
#               result_data[f'prompt{idx}']['db_text'] = db_string
#     print("resulting data: ")
#     print(result_data)
#     tool_context.state['camp_analysis_input'] = result_data
#     # save json in local as well 
#     json_output = json.dumps(result_data, indent =4)
#     with open("text_viz_json.json", "w") as f:
#         json.dump(json_output, f, indent=2)
#     return result_data

async def campaign_analysis_agent(tool_context: Optional[ToolContext] = None, **kwargs):
    # # print(tool_context.state)
    # session_id = tool_context.state.get("session_id")
    # print("The Session id is : ",session_id)
    # # print(f"session id inside text_viz_json: {session_id}")
    # bucket_name = os.getenv("BUCKET_NAME")
    # print("The Bucket name is : ",bucket_name)
    # # session_prefix = f'data_science/user/{session_id}/'
    # session_prefix = f'prompt_executor/user/{session_id}/'
    # # session_prefix = f'default-app-name/user/{session_id}/'

    # # Initialize client
    # client = storage.Client()
    # bucket = client.bucket(bucket_name)

    # # Step 1: List and sort all blobs
    # blobs = list(bucket.list_blobs(prefix=session_prefix))
    # print("The blobs are : ", blobs)
    # # Filter out unwanted blobs before sorting
    # filtered_blobs = [blob for blob in blobs if 'code_execution_image_' not in blob.name]
    # sorted_blobs = sorted(filtered_blobs, key=lambda b: b.updated)
    # print("The soreted_blobs are : ", sorted_blobs)
    # result =[]
    # for blob in sorted_blobs:
    #     content = blob.download_as_text()
    #     print("The content inside the blob is : ", content)
    #     result.append(content)
    # print("RESULT(Data inside all the files that are output of prompt generator)")
    # print(result)
    result = tool_context.state["db_ds_agent_output"] 
    print(result)
    # Execute analysis agent
    campaign_analysis_output = await run_campaign_analysis(
        result,
        tool_context
    )

    # Store output for downstream agents
    tool_context.state["campaign_analysis_output"] = campaign_analysis_output

    print("Campaign Analysis Completed.")

    return "Campaign Analysis Executed Successfully"


async def run_campaign_analysis(
    aggregated_results: list,
    tool_context: ToolContext
):
    """
    Executes the Campaign Analysis agent on aggregated DB results
    while conditioning on the original user question.
    """
    model = GenerativeModel(os.getenv("GEMINI_MODEL"))
    response = model.generate_content(
        aggregated_results,
        generation_config={
            "temperature": 0.5,
            "top_p": 1.0,
            "max_output_tokens": 2048
        }
    )
 
    try:
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"
    
    # agent_tool = AgentTool(agent=campaign_analysis_root_agent)

    # # Structured payload for analysis agent
    # analysis_payload = {
    #     "user_question": user_question,
    #     "db_results": aggregated_results,
    #     "analysis_type": "campaign_analysis"
    # }

    # response = await agent_tool.run_async(
    #     args={"request": json.dumps(analysis_payload)},
    #     tool_context=tool_context
    # )

    # return response


# async def call_campaign_analysis_agent(
#     tool_context: ToolContext,
# ):
#     """
#     Tool to trigger Campaign Analysis after DB/DS agent execution completes.
#     """

#     # Get DB results
#     aggregated_results = tool_context.state.get("db_ds_agent_output")

#     if not aggregated_results:
#         raise ValueError(
#             "db_ds_agent_output not found in state. Ensure prompt executor ran first."
#         )

#     # Get original user question
#     # user_question = tool_context.state.get("user_question")
#     user_question = ["What is the overall performance of Campaign ID: CMP_2025_0007 for Continental (CTR, Conversion, ROI)"]

#     if not user_question:
#         raise ValueError(
#             "user_question not found in state. Ensure it is stored at pipeline start."
#         )

#     print("Triggering Campaign Analysis Agent...")
#     print(f"User Question: {user_question}")
#     print(f"Aggregated Results Count: {len(aggregated_results)}")

#     # Execute analysis agent
#     campaign_analysis_output = await run_campaign_analysis(
#         aggregated_results,
#         user_question,
#         tool_context
#     )

#     # Store output for downstream agents
#     tool_context.state["campaign_analysis_output"] = campaign_analysis_output

#     print("Campaign Analysis Completed.")

#     return "Campaign Analysis Executed Successfully"