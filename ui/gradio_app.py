import gradio as gr
from google.cloud import bigquery
import pandas as pd
import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from prompt_generator.agent import build_prompt_from_input, generate_prompt_content
from summarizer.agent import summarize_insights
import re
import os

# === Config ===
load_dotenv()
ADK_AGENT_ID = "4850966136910512128"
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "acn-cda")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
ADK_AGENT_PATH = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ADK_AGENT_ID}"

vertexai.init(project=PROJECT_ID, location=LOCATION)

# === BQ setup ===
client = bigquery.Client()
QUERY = """
SELECT DISTINCT 
  brand, 
  platform_desc, 
  campaign_desc, 
  creative_desc 
FROM `acn-cda.mars_marketing_data.view_performance_table`
"""
df = client.query(QUERY).to_dataframe()
df.fillna("Unknown", inplace=True)

BRANDS = sorted(df['brand'].unique().tolist())
PLATFORMS = sorted(df['platform_desc'].unique().tolist())
DAYS = ["NA"] + [str(i) for i in range(1, 32)]
MONTHS = ["NA"] + ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"]
YEARS = ["NA"] + [str(y) for y in range(2000, 2026)]

# === Utility ===
def remove_explanation(text):
    patterns = [
        r"\bExplanation\s*[:\-]\s*",
        r"\bHere is an explanation\b",
        r"\bReasoning\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return text[:match.start()].strip()
    return text.strip()

def query_adk_parallel(prompts):
    remote_app = agent_engines.get(ADK_AGENT_PATH)
    user_id = "gradio_user"
    session = remote_app.create_session(user_id=user_id)
    session_id = session["id"]

    def single_query(prompt):
        events = remote_app.stream_query(
            user_id=user_id,
            session_id=session_id,
            message=prompt
        )
        all_parts = []
        for event in events:
            if "content" in event and "parts" in event["content"]:
                for part in event["content"]["parts"]:
                    if "text" in part:
                        all_parts.append(part["text"])
        final_response = "".join(all_parts)
        return remove_explanation(final_response)

    responses = []
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(single_query, p) for p in prompts]
        for f in as_completed(futures):
            try:
                responses.append(f.result())
            except Exception as e:
                responses.append(f"ERROR: {e}")
    return responses, session_id

def update_campaigns_and_creatives(brand, platform):
    filtered = df.copy()
    if brand != "All":
        filtered = filtered[filtered["brand"] == brand]
    if platform != "All":
        filtered = filtered[filtered["platform_desc"] == platform]

    campaigns = ["All"] + sorted(filtered["campaign_desc"].unique().tolist())
    creatives = ["All"] + sorted(filtered["creative_desc"].unique().tolist())
    return gr.update(choices=campaigns, value=["All"]), gr.update(choices=creatives, value=["All"])

def full_workflow_run(brand, platform, campaigns, creatives,
                      start_day, start_month, start_year,
                      end_day, end_month, end_year):
    start_date = None
    end_date = None

    if "NA" not in [start_day, start_month, start_year]:
        start_date = f"{start_year}-{str(MONTHS.index(start_month)).zfill(2)}-{start_day.zfill(2)}"
    if "NA" not in [end_day, end_month, end_year]:
        end_date = f"{end_year}-{str(MONTHS.index(end_month)).zfill(2)}-{end_day.zfill(2)}"

    campaigns = ["All"] if not campaigns or "All" in campaigns else campaigns
    creatives = ["All"] if not creatives or "All" in creatives else creatives

    user_input = {
        "brand": brand,
        "platform": platform,
        "campaign": campaigns,
        "creative": creatives,
        "start_date": start_date if start_date else "<ALL>",
        "end_date": end_date if end_date else "<ALL>"
    }

    instruction_text = build_prompt_from_input(user_input)
    prompts = generate_prompt_content(instruction_text)

    if not prompts:
        return "Failed to generate narrative prompts.", None

    adk_responses, session_id = query_adk_parallel(prompts)

    # Save prompts to a file using session_id
    filename = f"generated_prompts_session_{session_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for i, prompt in enumerate(prompts, 1):
            f.write(f"Prompt {i}:\n{prompt}\n\n")

    summary = summarize_insights(adk_responses)
    return summary, filename

# === Gradio UI ===
with gr.Blocks(theme=gr.themes.Base(primary_hue="purple")) as demo:
    gr.HTML("""
    <style>
    body, .gradio-container {
        background-color: #5C2D91;
    }
    #accenture-logo {
        display: block;
        margin-left: auto;
        margin-right: auto;
    }
    h1, h2, h3, label {
        color: white !important;
    }
    </style>
    """)

    gr.Image(value="download.png", elem_id="accenture-logo", height=80)
    gr.Markdown("# Business Narrative Generator")

    with gr.Accordion("Input Filters", open=True):
        with gr.Row():
            brand_input = gr.Dropdown(["All"] + BRANDS, label="Brand", value="All")
            platform_input = gr.Dropdown(["All"] + PLATFORMS, label="Platform", value="All")

        with gr.Row():
            campaign_input = gr.Dropdown(["All"], label="Campaigns", multiselect=True, value=["All"])
            creative_input = gr.Dropdown(["All"], label="Creatives", multiselect=True, value=["All"])

        gr.Markdown("#### Start Date")
        with gr.Row():
            start_day = gr.Dropdown(DAYS, label="Day", value="NA")
            start_month = gr.Dropdown(MONTHS, label="Month", value="NA")
            start_year = gr.Dropdown(YEARS, label="Year", value="NA")

        gr.Markdown("#### End Date")
        with gr.Row():
            end_day = gr.Dropdown(DAYS, label="Day", value="NA")
            end_month = gr.Dropdown(MONTHS, label="Month", value="NA")
            end_year = gr.Dropdown(YEARS, label="Year", value="NA")

    generate_btn = gr.Button(" Generate Narrative")

    output_box = gr.Textbox(label="Final Narrative", lines=20, interactive=False)
    file_output = gr.File(label="Download Prompt File", visible=True)

    brand_input.change(fn=update_campaigns_and_creatives,
                       inputs=[brand_input, platform_input],
                       outputs=[campaign_input, creative_input])

    platform_input.change(fn=update_campaigns_and_creatives,
                          inputs=[brand_input, platform_input],
                          outputs=[campaign_input, creative_input])

    generate_btn.click(fn=full_workflow_run,
                       inputs=[brand_input, platform_input, campaign_input, creative_input,
                               start_day, start_month, start_year,
                               end_day, end_month, end_year],
                       outputs=[output_box, file_output])

demo.launch(server_name="0.0.0.0", server_port=8000)
