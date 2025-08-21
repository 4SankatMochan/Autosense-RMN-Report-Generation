 daimport os
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines

def test_business_insight_agent():
    """
    Tests if the Business_Insight_Agent is deployed correctly and responds to test queries.
    """
    load_dotenv()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "acn-cda")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    app_name = "Business_Insight_Agent"
    agent_engine_id = "6993553659632025600"
    agent_path = f"projects/{project_id}/locations/{location}/reasoningEngines/{agent_engine_id}"
    user_id = "u_business_insight_test"
    staging_bucket = f"gs://{project_id}-bucket"

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )

    try:
        remote_app = agent_engines.get(agent_path)
        print(f" Agent loaded: {remote_app.display_name} (ID: {remote_app.name})")
    except Exception as e:
        print(f" ERROR: Could not get agent engine: {e}")
        return

    try:
        session = remote_app.create_session(user_id=user_id)
        session_id = session["id"]
        print(f"Session created: {session_id}")
    except Exception as e:
        print(f"ERROR: Failed to create session: {e}")
        return

    test_messages = [
        "Give me descriptive insights for the Twix brand.",
        "What was the total actual spend across all platforms for M&M brand in June 2024?",
    ]

    print("\n--- Agent Responses ---")
    for message in test_messages:
        print(f"\n Query: {message}")
        try:
            events = remote_app.stream_query(
                user_id=user_id,
                session_id=session_id,
                message=message
            )

            response_text = ""
            for event in events:
                if "content" in event and "parts" in event["content"]:
                    for part in event["content"]["parts"]:
                        if "text" in part:
                            response_text += part["text"]
            print(f" Response:\n{response_text.strip()}")
        except Exception as e:
            print(f"ERROR during stream_query: {e}")

    # Optional: Cleanup session
    try:
        remote_app.delete_session(user_id=user_id, session_id=session_id)
        print(f"\n Session {session_id} cleaned up.")
    except Exception as e:
        print(f"WARNING: Failed to delete session: {e}")

if __name__ == "__main__":
    test_business_insight_agent()
