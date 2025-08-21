import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv
from prompt_generator.agent import build_prompt_from_input, generate_prompt_content
import os

# === Config ===
load_dotenv()
ADK_AGENT_ID = "8195399033628393472"
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "acn-cda")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
ADK_AGENT_PATH = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ADK_AGENT_ID}"

vertexai.init(project=PROJECT_ID, location=LOCATION)

def query_adk_test(prompts):
    remote_app = agent_engines.get(ADK_AGENT_PATH)
    user_id = "test_user"
    session_id = remote_app.create_session(user_id=user_id)["id"]

    for prompt in prompts:
        print("\n--- Sending prompt to ADK ---")
        print(prompt)
        parts = []
        try:
            events = remote_app.stream_query(user_id=user_id, session_id=session_id, message=prompt)
            for event in events:
                if "content" in event:
                    if "parts" in event["content"]:
                        for part in event["content"]["parts"]:
                            if "text" in part:
                                parts.append(part["text"])
            full_response = "".join(parts)
            print("\n--- ADK Response ---")
            print(full_response)
        except Exception as e:
            print(f"❌ Error querying ADK: {e}")

# === TEST DATA ===
user_input = {
    "brand": "Snickers",
    "platform": "Facebook Ads",
    "campaign": ["All"],
    "creative": ["All"],
    "start_date": "2024-03-05",
    "end_date": "2024-07-10"
}

# === Build prompt ===
instruction_text = build_prompt_from_input(user_input)
prompts = generate_prompt_content(instruction_text)

if not prompts:
    print("❌ Failed to generate prompts.")
else:
    query_adk_test(prompts)
