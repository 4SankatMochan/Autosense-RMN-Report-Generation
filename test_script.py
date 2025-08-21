import os
import re
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines
from concurrent.futures import ThreadPoolExecutor, as_completed
 
def remove_explanation(text):
    """
    Removes any explanation part from the ADK output.
    Looks for common markers like 'Explanation:', 'Explanation -', etc.
    """
    explanation_patterns = [
        r"\bExplanation\s*[:\-]\s*",      # matches 'Explanation:', 'Explanation -'
        r"\bHere is an explanation\b",    # matches 'Here is an explanation'
        r"\bReasoning\b",                 # matches 'Reasoning'
    ]
 
    for pattern in explanation_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return text[:match.start()].strip()
 
    return text.strip()
 
def query_data_science_agent(
    remote_app: agent_engines.AgentEngine,
    user_id: str,
    session_id: str,
    input_messages: list
) -> list:
    """
    Queries a Vertex AI Data Science Agent concurrently with a list of input messages
    and returns a list of consolidated responses without explanations.
    """
 
    def _single_query(message: str) -> str:
        """Helper function to execute a single query for concurrent execution."""
        print(f"\n--- Querying agent for message: '{message}' (via stream_query and collecting results) ---")
        try:
            events = remote_app.stream_query(
                user_id=user_id,
                session_id=session_id,
                message=message,
            )
 
            all_response_text_parts = []
            has_content_event_received = False
 
            for event in events:
                if "content" in event:
                    has_content_event_received = True
                    if "parts" in event["content"]:
                        for part in event["content"]["parts"]:
                            if "text" in part:
                                all_response_text_parts.append(part["text"])
 
            if all_response_text_parts:
                final_consolidated_response = "".join(all_response_text_parts)
                final_cleaned_response = remove_explanation(final_consolidated_response)
 
                print(f"--- Final Consolidated Agent Response for '{message}' ---")
                print(final_cleaned_response)
                return final_cleaned_response
 
            elif has_content_event_received:
                print(f"--- Agent finished for '{message}', but no 'text' content found in any 'content' events. ---")
                return "No text content found in response."
 
            else:
                print(f"--- Agent finished for '{message}', but no 'content' events were received. ---")
                return "No content events received from agent."
 
        except Exception as e:
            print(f"ERROR: An error occurred during the query for message '{message}': {e}")
            return f"ERROR: {e}"
 
    all_responses = []
    with ThreadPoolExecutor() as executor:
        future_to_message = {executor.submit(_single_query, msg): msg for msg in input_messages}
 
        for future in as_completed(future_to_message):
            msg = future_to_message[future]
            try:
                response = future.result()
                all_responses.append(response)
            except Exception as exc:
                print(f"ERROR: Message '{msg}' generated an exception: {exc}")
                all_responses.append(f"ERROR: {exc}")
 
    return all_responses
 
# Example usage:
if __name__ == "__main__":
    load_dotenv()
 
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "acn-cda")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    app_name = os.environ.get("APP_NAME", "DATA_SCIENCE_AGENT_ADK")
    bucket_name = f"gs://{project_id}-bucket002"
 
    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=bucket_name,
    )
 
    AGENT_ENGINE_ID = '4850966136910512128'
    AGENT_ENGINE_RESOURCE_NAME = f"projects/{project_id}/locations/{location}/reasoningEngines/{AGENT_ENGINE_ID}"
 
    try:
        remote_app = agent_engines.get(AGENT_ENGINE_RESOURCE_NAME)
    except Exception as e:
        print(f"ERROR: Failed to get agent engine {AGENT_ENGINE_RESOURCE_NAME}: {e}")
        print(f"INFO: Attempting to list agent engines to find '{app_name}' as a fallback.")
        ae_apps = agent_engines.list(filter=f'display_name="{app_name}"')
        remote_app = next(ae_apps, None)
        if remote_app is None:
            print(f"CRITICAL: Could not find agent engine with ID '{AGENT_ENGINE_ID}' or display name '{app_name}'. Exiting.")
            exit(1)
 
    print(f"INFO: Using remote agent engine: {remote_app.display_name} (ID: {remote_app.name.split('/')[-1]})")
 
    USER_ID = "test_descriptive"
    remote_session = remote_app.create_session(user_id=USER_ID)
    SESSION_ID = remote_session["id"]
 
    messages_to_query = [
        "Give me descriptive insights for brand snickers",
        "What was the Video plays for the Balisto brand's and Snapchat Ads, across all creatives?",
        "State the total number of clicks accumulated across all creatives for the 5 Gum brand's campaign 'DE_5 Gum_mw_eur_Dv360_102' on the DV 360 platform."
    ]
 
    responses = query_data_science_agent(remote_app, USER_ID, SESSION_ID, messages_to_query)
 
    print("\n--- All Responses ---")
    for i, response in enumerate(responses):
        print(f"Response for message {i+1}:\n{response}\n")
        print("--------------------------------------------------******-----------------------------------------------------")