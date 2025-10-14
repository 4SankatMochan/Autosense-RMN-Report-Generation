from google.cloud import storage
import base64
import os

def return_instructions_json(
    ) -> str:
  
    prompt = f"""You are a formatter agent. Your job is to call your tool `text_viz_json`.
It takes only the tool context and fetches artifacts from the GCS bucket.
All required arguments to fetch the artifacts are already defined inside `text_viz_json`."""

    return prompt