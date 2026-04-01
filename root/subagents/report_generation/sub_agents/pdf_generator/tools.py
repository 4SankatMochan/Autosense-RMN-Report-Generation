# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import uuid
import base64
import json
import re

from google.adk.tools import ToolContext
from .pdf_generator_func import GCSJSONToPDF as JSONToPDF
from google.cloud import storage
from collections import defaultdict
from typing import List, Optional
import time

def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe as a filename."""
    name = name.lower().strip()
    # Replace spaces with underscores
    name = re.sub(r"\s+", "_", name)
    # Remove any character that is not alphanumeric, underscore or hyphen
    name = re.sub(r"[^\w\-]", "", name)
    # Limit length for safety
    return name[:50] if len(name) > 50 else name

async def setup_report_context(tool_context):
    """
    Prepare state before report generation.
    """

    tool_context.state["persona_context"] = ""

    session_id = tool_context._invocation_context.session.id
    user_id = tool_context._invocation_context.user_id

    tool_context.state["session_id"] = session_id
    tool_context.state["user_id"] = user_id

    print(f"Report context setup → session_id: {session_id}")
    print(f"Report context setup → user_id: {user_id}")

    return "Context initialized"
    # Generates a PDF report from chart data stored in tool_context.state.
async def generate_pdf_report(tool_context: Optional[ToolContext] = None):    
    """

    Args:
        tool_context (ToolContext): The tool context with state.

    Returns:
        str: Path to the generated PDF file or an error message.
    """
    # await setup_report_context(tool_context)
    session_id = str(tool_context.state["session_id"])
    try:
        print(f"session id inside tool generate report inside pdf generator: {str(tool_context.state["session_id"])}")
    except:
        print("no session id inside tool generate report inside pdf generator")
    try:
        # Get JSON input from tool context state
        json_input = tool_context.state.get("report_json")

        import json
        #json_input = json.loads(json_input.strip("```json"))
        print("report json in pdf generator")
        print(json_input)
        
        if not json_input:
            return "No data found in tool context state under 'viz_smry_json'."

        # Attempt to extract a report name from the JSON (e.g., heading or title)
        # report_name = None
        # if 'context' in json_input and isinstance(json_input['context'], str) and json_input['context'].strip():
        #     report_name = json_input['context'].strip()


        # if not report_name:
        #     report_name = f"chart_report_{uuid.uuid4().hex[:8]}"
        # else:
        #     report_name = sanitize_filename(report_name)

        output_dir = "./output"
        os.makedirs(output_dir, exist_ok=True)
        pdf_generator = JSONToPDF(output_dir=output_dir)
        session_id = tool_context.state["session_id"]
        user_id = tool_context.state["user_id"]
        print(f"user_id : {user_id}")
        output_filename = f"gs://acn-cda-adk-staging/root/user/{session_id}/final_report.pdf"
        clickable_filename = f"https://storage.cloud.google.com/acn-cda-adk-staging/root/user/{session_id}/final_report.pdf"
        output_path = pdf_generator.generate_pdf(json_input, gcs_pdf_path = output_filename, clikable_path= clickable_filename)
        print('PDF end time',time.strftime('%H:%M:%S'))
        return output_path, clickable_filename
    except Exception as e:
        return f"An error occurred while generating the PDF: {str(e)}"
