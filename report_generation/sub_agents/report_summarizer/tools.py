

from google import genai
from google.genai import types
import os
from .prompts import generate_report_prompt, format_report_prompt
from typing import List, Optional
import os
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel


template = """# [Report Title]

## 1. Executive Summary
## 2. Introduction
### 2.1. Background
### 2.2. Report Objectives
## 3. Channel Performance Overview
### 3.1. Distinct Channels Identified
### 3.2. Total Attributed Sales by Channel
## 4. Daily Performance Analysis
### 4.1. Daily Attributed Sales Value
## 5. Conclusion and Recommendations
"""

context = """This report is prepared for the Marketing and Sales leadership team to provide a comprehensive overview of campaign performance across different channels. The primary objective is to understand which channels contribute most effectively to attributed sales and to identify overall daily sales patterns. The insights derived from this analysis will be crucial in informing strategic decisions related to optimizing future marketing spend, resource allocation, and campaign targeting to maximize ROI.
"""
context="""nil
"""
filters = """nil
"""

def llm_call(prompt):
    model = GenerativeModel(os.getenv("TEXT_VIZ_JSON_AGENT"))
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.5,
            "top_p": 1.0,
            "max_output_tokens": 2048
        }
    )
    # print(f"llm response")
    # print(response)
    try:
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"

async def generate_report(tool_context: Optional[ToolContext] = None):
  """ Generates report in Markdown format.
  """
  print("inside report summarization agent")
  print("inside generate report tool")
  summary = tool_context.state['text_viz_json']
  template = tool_context.state['report_template']
  print(f"text_viz_json output: {summary}")
  print(f"report template passed: {template}")
  main_prompt = generate_report_prompt()
  custom_prompt = f"""
**Task**
Generate report based on the below information.

**Input Parameters:**
1.  **Text and Visualization Summary:**

    {summary}

2.  **Report Template:**

    {template}

3.  **Report Context:**

    {context}

4.  **Filters:**

    {filters}

**Output:**
  """
  prompt = main_prompt + custom_prompt
  res = llm_call(prompt)
  tool_context.state['report_markdown'] = res
  print("report markdown generated:")
  print(res)
  return "report markdown generated"
  

async def format_report(tool_context: Optional[ToolContext] = None):
  """Convert Report from markdown format to JSON format
  """
  print("inside format report tool")
  report = tool_context.state['report_markdown']
  main_prompt = format_report_prompt()
  custom_prompt = f"""
**Task**
Generate JSON from the Report given below. Do not violate safety filters while generating output. Remove just the things that violate safety rules and kept  of all the information in the Report.

**Report:**

{report}

**Output:**
  """
  prompt = main_prompt + custom_prompt
  res = llm_call(prompt)
  tool_context.state['report_json'] = res
  print("report json generated: ")
  print(res)
  return "report formatted to json"



























from google.cloud import storage
import base64
import json
import re
from collections import defaultdict
from typing import List, Optional
import os
from google.adk.tools import ToolContext

async def text_viz_json(tool_context: Optional[ToolContext] = None):
    session_id = tool_context.state.get("session_id")
    bucket_name = os.getenv("BUCKET_NAME")
    session_prefix = f'data_science/user/{session_id}/'

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
    tool_context.state['text_viz_json'] = result_data
    # save json in local as well 
    json_output = json.dumps(result_data, indent =4)
    with open("text_viz_json.json", "w") as f:
        json.dump(json_output, f, indent=2)
    return result_data
