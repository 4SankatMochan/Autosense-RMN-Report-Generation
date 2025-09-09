import pandas as pd
import requests
import uuid
from sentence_transformers import SentenceTransformer, util

# ========================
# Config
# ========================
BASE_URL = "http://127.0.0.1:8000"   # poetry run adk web ke baad
APP_NAME = "data_science"
USER_ID = "user"

INPUT_FILE = "test_cases.xlsx"       # user-provided queries + expected outputs
OUTPUT_FILE = "evaluation_results.xlsx"
SIMILARITY_THRESHOLD = 0.8           # Pass/Fail threshold

# ========================
# Init
# ========================
print("Loading model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

def compute_similarity(a, b):
    """Compute semantic similarity between expected and generated outputs"""
    if not a or not b:
        return 0.0
    emb1 = model.encode(str(a), convert_to_tensor=True)
    emb2 = model.encode(str(b), convert_to_tensor=True)
    return util.cos_sim(emb1, emb2).item()

def create_session():
    """Create a new session and return sessionId"""
    try:
        resp = requests.post(f"{BASE_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions")
        resp.raise_for_status()
        session_id = resp.json().get("id") or str(uuid.uuid4())
        return session_id
    except Exception as e:
        print(f"Session create failed, using fallback UUID: {e}")
        return str(uuid.uuid4())

def extract_output(resp_json):
    """Parse ADK /run response and extract clean text output"""
    if isinstance(resp_json, dict):
        return resp_json.get("output")

    elif isinstance(resp_json, list):
        for item in resp_json:
            if isinstance(item, dict):
                content = item.get("content", {})
                if isinstance(content, dict):
                    parts = content.get("parts", [])
                    if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                        return parts[0]["text"]
    # fallback
    return str(resp_json)

# ========================
# Load test cases
# ========================
print(f"Reading test cases from {INPUT_FILE}...")
df = pd.read_excel(INPUT_FILE)

if "query" not in df.columns or "expected_output" not in df.columns:
    raise ValueError("Input Excel must have 'query' and 'expected_output' columns")

generated_outputs = []
similarities = []
statuses = []
raw_responses = []

# ========================
# Run evaluation
# ========================
print("Running evaluation...")

for idx, row in df.iterrows():
    query = row["query"]
    expected = row["expected_output"]

    # Step 1: Create session
    session_id = create_session()

    try:
        # Step 2: Run query in session
        payload = {
            "appName": APP_NAME,
            "userId": USER_ID,
            "sessionId": session_id,
            "newMessage": {
                "parts": [{"text": query}],
                "role": "user"
            },
            "streaming": False
        }

        resp = requests.post(f"{BASE_URL}/run", json=payload)
        resp.raise_for_status()
        resp_json = resp.json()
        raw_responses.append(str(resp_json))

        # Step 3: Extract clean output
        gen_output = extract_output(resp_json)

    except Exception as e:
        gen_output = f"Error: {e}"
        raw_responses.append(str(gen_output))

    # Step 4: Evaluate
    sim = compute_similarity(expected, gen_output)
    status = "PASS" if sim >= SIMILARITY_THRESHOLD else "FAIL"

    generated_outputs.append(gen_output)
    similarities.append(round(sim, 3))
    statuses.append(status)

    print(f"[{status}] Query: {query} | Similarity: {sim:.3f}")

# ========================
# Save results
# ========================
df["generated_output"] = generated_outputs
df["similarity_score"] = similarities
df["status"] = statuses
df["raw_response"] = raw_responses  # debug column

df.to_excel(OUTPUT_FILE, index=False)
print(f"\n Evaluation completed. Results saved to {OUTPUT_FILE}")
