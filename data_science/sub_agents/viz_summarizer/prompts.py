from google.cloud import storage
import base64
import os

def return_instructions_dv_smry(
    ) -> str:
  
    prompt = f"""You are a visualization summarizer. Your job is to call your tool `viz_artifact_formatter`.
It takes only the tool context and fetches visualization artifacts from the GCS bucket.
All required arguments to fetch the artifacts are already defined inside `viz_artifact_formatter`."""

    return prompt