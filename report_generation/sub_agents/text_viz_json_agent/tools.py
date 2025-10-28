from google.cloud import storage
import base64
import json
import re
from collections import defaultdict
from typing import List, Optional
import os
from google.adk.tools import ToolContext

async def text_viz_json(tool_context: Optional[ToolContext] = None):
    print("inside text_viz_json agent")
    # print(tool_context.state)
    session_id = tool_context.state.get("session_id")
    # print(f"session id inside text_viz_json: {session_id}")
    bucket_name = os.getenv("BUCKET_NAME")
    # session_prefix = f'data_science/user/{session_id}/'
    session_prefix = f'root/user/{session_id}/'
    # session_prefix = f'default-app-name/user/{session_id}/'

    # Initialize client
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Step 1: List and sort all blobs
    blobs = list(bucket.list_blobs(prefix=session_prefix))
    # Filter out unwanted blobs before sorting
    filtered_blobs = [blob for blob in blobs if 'code_execution_image_' not in blob.name]
    sorted_blobs = sorted(filtered_blobs, key=lambda b: b.updated)

    # Step 2: Group blobs by base path (without /N), keep highest version
    blob_versions = defaultdict(list)
    versioned_blob_pattern = re.compile(r'(.+?)(?:/(\d+))$')  # Extract base path and version number

    for blob in sorted_blobs:
        match = versioned_blob_pattern.match(blob.name)
        if match:
            base_path = match.group(1)
            version = int(match.group(2))
            blob_versions[base_path].append((version, blob))

    # Step 3: Select highest version for each base path
    latest_blobs = {}
    for base_path, versions in blob_versions.items():
        # Pick the blob with max version number
        latest_blob = max(versions, key=lambda x: x[0])[1]
        latest_blobs[base_path] = latest_blob

    # Step 4: Identify prompts from .json and .png files
    prompt_map = defaultdict(dict)
    for base_path, blob in latest_blobs.items():
        filename = base_path.split('/')[-1]
        if filename.endswith('_data.json'):
            prompt = filename.replace('_data.json', '')
            prompt_map[prompt]['json_blob'] = blob
        elif filename.endswith('_VizChart.png'):
            prompt = filename.replace('_VizChart.png', '')
            prompt_map[prompt]['chart_blob'] = blob
        elif filename.endswith('_viz_ds_agent.txt'):
            prompt = filename.replace('_viz_ds_agent.txt', '')
            prompt_map[prompt]['viz_ds_text'] = blob
        elif filename.endswith('_viz_agent.txt'):
            prompt = filename.replace('_viz_agent.txt', '')
            prompt_map[prompt]['viz_text'] = blob
        elif filename.endswith('_db_agent.txt'):
            prompt = filename.replace('_db_agent.txt', '')
            prompt_map[prompt]['db_text'] = blob
        elif filename.endswith('_ds_agent.txt'):
            prompt = filename.replace('_ds_agent.txt', '')
            prompt_map[prompt]['ds_text'] = blob

    # Step 5: Build result_data
    result_data = {}
    for idx, (prompt, blobs_dict) in enumerate(prompt_map.items(), start=1):
        json_blob = blobs_dict.get('json_blob')
        chart_blob = blobs_dict.get('chart_blob')
        # viz_ds_blob = blobs_dict.get('viz_ds_text')
        viz_blob = blobs_dict.get('viz_text')
        db_blob =  blobs_dict.get('db_text')
        ds_blob =  blobs_dict.get('ds_text')

        result_data[f'prompt{idx}'] = {
            'prompt': prompt.replace("_"," "),
            'chart_url': None,
            'json_data': None,
            'viz_text': None,
            # 'viz_ds_text': None,
            'db_text': None,
            'ds_text': None
        }

        # Download chart if present
        if chart_blob:              # If chart is availabe
            result_data[f'prompt{idx}']['chart_url'] = f'gs://{bucket_name}/{chart_blob.name}'
            # Download JSON if present
            if json_blob:
                result_data[f'prompt{idx}']['json_data'] = f'gs://{bucket_name}/{json_blob.name}'
                # Download viz agent text if present
            if viz_blob:
                viz_string = viz_blob.download_as_text()
                result_data[f'prompt{idx}']['viz_text'] = viz_string
            ## Need Alignment: Do we need to add db_text and ds_text as well in chart
        elif ds_blob:
            ds_string = ds_blob.download_as_text()
            result_data[f'prompt{idx}']['ds_text'] = ds_string


        elif db_blob:
            db_string = db_blob.download_as_text()
            try:
              # Remove markdown formatting lines if present
              if db_string.startswith("```json"):
                  db_string = db_string.split("\n", 1)[1]  # Remove first line
              if db_string.endswith("```"):
                  db_string = db_string.rsplit("\n", 1)[0]  # Remove last line

              # Now parse the cleaned JSON string
              data = json.loads(db_string)

              # Extract channel names from `nl_results`
              nl_text = data["nl_results"]
              result_data[f'prompt{idx}']['db_text'] = nl_text
            except:
              result_data[f'prompt{idx}']['db_text'] = db_string
    print("resulting text_viz_json: ")
    print(result_data)
    tool_context.state['text_viz_json'] = result_data
    # save json in local as well 
    json_output = json.dumps(result_data, indent =4)
    with open("text_viz_json.json", "w") as f:
        json.dump(json_output, f, indent=2)
    return result_data
