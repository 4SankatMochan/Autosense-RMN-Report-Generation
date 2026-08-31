"""
Deploy RMN Report Gen agent to Vertex AI Agent Engine.

Run from Google Cloud Shell (no Windows path issues, already authenticated):
    # First time deploy:
    python deployment_script.py

    # Update an existing deployment:
    python deployment_script.py --update projects/350875723330/locations/us-central1/reasoningEngines/6514040695840309248
"""
# Fix Accenture/Zscaler corporate SSL proxy — must be before all other imports
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # Cloud Shell / Linux doesn't need this
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME       = "report-gen-v2"
EXTRA_PACKAGES = ["./root"]

ROOT_DIR = Path(__file__).parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

PROJECT_ID     = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION       = os.getenv("GOOGLE_CLOUD_LOCATION")
STAGING_BUCKET = os.getenv("GOOGLE_CLOUD_STAGING_BUCKET")

if not all([PROJECT_ID, LOCATION, STAGING_BUCKET]):
    missing = [k for k, v in {
        "GOOGLE_CLOUD_PROJECT":        PROJECT_ID,
        "GOOGLE_CLOUD_LOCATION":       LOCATION,
        "GOOGLE_CLOUD_STAGING_BUCKET": STAGING_BUCKET,
    }.items() if not v]
    raise ValueError(f"Missing env vars: {', '.join(missing)}")

vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    staging_bucket=f"gs://{STAGING_BUCKET}",
)

# ── Requirements ──────────────────────────────────────────────────────────────
def load_requirements(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

requirements = load_requirements(ROOT_DIR / "requirements.txt")

# ── ADK App ───────────────────────────────────────────────────────────────────
from root.agent import root_agent  # noqa: E402 – imported after vertexai.init

adk_app = AdkApp(agent=root_agent, enable_tracing=False)

# ── Runtime env vars injected into the Agent Engine container ─────────────────
env_vars = {k: v for k, v in {
    "GOOGLE_GENAI_USE_VERTEXAI":       os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "1"),
    # GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are reserved by Agent Engine — injected automatically
    "NL2SQL_METHOD":                   os.getenv("NL2SQL_METHOD", "BASELINE"),
    "BQ_PROJECT_ID":                   os.getenv("BQ_PROJECT_ID"),
    "BQ_DATASET_ID":                   os.getenv("BQ_DATASET_ID"),
    "BQ_TABLE_ID":                     os.getenv("BQ_TABLE_ID"),
    "GOOGLE_CLOUD_STORAGE_BUCKET":     os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET"),
    "BUCKET_NAME":                     os.getenv("BUCKET_NAME"),
    "ARTIFACT_SERVICE_URI":            os.getenv("ARTIFACT_SERVICE_URI"),
    "BQML_RAG_CORPUS_NAME":            os.getenv("BQML_RAG_CORPUS_NAME"),
    "CODE_INTERPRETER_EXTENSION_NAME": os.getenv("CODE_INTERPRETER_EXTENSION_NAME"),
    "ROOT_AGENT_MODEL":                os.getenv("ROOT_AGENT_MODEL", "gemini-2.5-flash"),
    "ANALYTICS_AGENT_MODEL":           os.getenv("ANALYTICS_AGENT_MODEL", "gemini-2.5-flash"),
    "BIGQUERY_AGENT_MODEL":            os.getenv("BIGQUERY_AGENT_MODEL", "gemini-2.5-flash"),
    "BASELINE_NL2SQL_MODEL":           os.getenv("BASELINE_NL2SQL_MODEL", "gemini-2.5-flash"),
    "CHASE_NL2SQL_MODEL":              os.getenv("CHASE_NL2SQL_MODEL", "gemini-2.5-flash"),
    "BQML_AGENT_MODEL":                os.getenv("BQML_AGENT_MODEL", "gemini-2.5-flash"),
    "VIZ_AGENT_MODEL":                 os.getenv("VIZ_AGENT_MODEL", "gemini-2.5-flash"),
    "PROMPT_EXECUTOR_AGENT_MODEL":     os.getenv("PROMPT_EXECUTOR_AGENT_MODEL", "gemini-2.5-flash"),
    "TEXT_VIZ_JSON_AGENT":             os.getenv("TEXT_VIZ_JSON_AGENT", "gemini-2.5-flash"),
    "SEQUENTIAL_AGENT":                os.getenv("SEQUENTIAL_AGENT", "gemini-2.5-flash"),
    "PDF_GENERATOR_AGENT_MODEL":       os.getenv("PDF_GENERATOR_AGENT_MODEL", "gemini-2.5-flash"),
    "GEMINI_MODEL":                    os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "persona_file_path":               os.getenv("persona_file_path"),
    "persona_report_map_path":         os.getenv("persona_report_map_path"),
}.items() if v is not None}

# ── Deploy / Update ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Deploy RMN agent to Vertex AI Agent Engine")
parser.add_argument(
    "--update",
    metavar="RESOURCE_NAME",
    help=(
        "Resource name of existing deployment to update. "
        "e.g. projects/350875723330/locations/us-central1/reasoningEngines/6514040695840309248"
    ),
)
args = parser.parse_args()

import time
import concurrent.futures


def _find_engine_by_name(display_name):
    """Return the most recently created engine matching display_name, or None."""
    matches = [e for e in agent_engines.list() if e.display_name == display_name]
    return matches[-1] if matches else None


def _wait_for_engine(display_name, max_wait=1800, interval=30):
    """Poll until an engine with display_name exists. Returns it or raises."""
    print(f"  Polling for '{display_name}' (up to {max_wait//60} min) ...")
    elapsed = 0
    while elapsed < max_wait:
        engine = _find_engine_by_name(display_name)
        if engine:
            return engine
        time.sleep(interval)
        elapsed += interval
        print(f"  Still waiting ... ({elapsed}s elapsed)")
    raise TimeoutError(f"Engine '{display_name}' not found after {max_wait}s")


RESOURCE_LIMITS = {"memory": "4Gi", "cpu": "4"}

if args.update:
    print(f"Updating existing agent engine: {args.update}")
    remote_app = agent_engines.get(args.update)
    try:
        deployed = remote_app.update(
            agent_engine=adk_app,
            requirements=requirements,
            extra_packages=EXTRA_PACKAGES,
            env_vars=env_vars,
            resource_limits=RESOURCE_LIMITS,
        )
    except (TimeoutError, concurrent.futures.TimeoutError):
        print("⏳ SDK polling timed out — the update is still running on GCP.")
        print("   Check status at: https://console.cloud.google.com/vertex-ai/agents")
        print(f"   Resource: {args.update}")
        exit(0)
else:
    print(f"Creating new agent engine: {APP_NAME} ...")
    try:
        deployed = agent_engines.create(
            agent_engine=adk_app,
            display_name=APP_NAME,
            requirements=requirements,
            extra_packages=EXTRA_PACKAGES,
            env_vars=env_vars,
            resource_limits=RESOURCE_LIMITS,
        )
    except (TimeoutError, concurrent.futures.TimeoutError):
        print("⏳ SDK polling timed out after 900s — deployment is still running on GCP.")
        print("   Polling manually for up to 30 more minutes ...")
        deployed = _wait_for_engine(APP_NAME)

print(f"\n✅ Done!")
print(f"   Resource name : {deployed.resource_name}")
print(f"   To update later, run:")
print(f"   python deployment_script.py --update {deployed.resource_name}")