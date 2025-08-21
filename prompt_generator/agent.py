from google import genai
from google.genai import types
import json
import re

# Utility to clean and fix JSON string
def fix_json_string(raw):
    # Remove any text before JSON array starts
    raw = re.sub(r'^[^\[]*', '', raw, flags=re.DOTALL)
    # Remove any text after JSON array ends
    raw = re.sub(r'\][^\]]*$', ']', raw, flags=re.DOTALL)
    # Ensure it starts and ends correctly
    if not raw.startswith("["):
        raw = "[" + raw
    if not raw.endswith("]"):
        raw += "]"
    return raw

# Build the instruction template
PROMPT_TEMPLATE = """
User Selections:
Brand: {brand_dd}
Campaign: {campaign_dd}
Creative: {creative_dd}
Platform: {platform_dd}
Start Date: {start_date}
End Date: {end_date}

Instructions:
If the values of Brand, Campaign, Creative, and Platform are <ALL>, consider all possible values based on the input BigQuery table. Otherwise, focus specifically on the selected entities.
Generate business narrative prompts for each KPI listed below, incorporating all user selections. Ensure each prompt is easy to understand and covers every minor detail.

KPIs:
impressions
frequency
reach
clicks
ctr_percent
conversions
conversion_rate_percent
actual_spend_to_date
attributed_sales_value
roas
cpc
cpa
video_starts
video_plays
video_first_quartile
video_midpoint
video_third_quartile
video_completions
video_completion_rate_percent
avg_watch_time
add_to_cart_events
new_to_brand_conversions
dwell_time
gross_rating_point
target_audience_rating_point
delivered_messages
message_opens
unsubscribe_bounce_rates

Return EXACTLY a valid JSON array of strings.
No extra text before or after.
Do not stop midway.
Ensure JSON is complete and parsable.
"""

def build_prompt_from_input(user_input):
    return PROMPT_TEMPLATE.format(
        brand_dd=user_input["brand"],
        campaign_dd=user_input["campaign"],
        creative_dd=user_input["creative"],
        platform_dd=user_input["platform"],
        start_date=user_input["start_date"],
        end_date=user_input["end_date"],
    )

def generate_prompt_content(instruction_text):
    client = genai.Client(
        vertexai=True,
        project="acn-cda",
        location="global",
    )
    model_name = "gemini-2.5-pro"

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=instruction_text)]
        )
    ]

    config = types.GenerateContentConfig(
        temperature=0.3,
        top_p=1.0,
        max_output_tokens=4096,  # Increased for bigger output
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
        ],
        thinking_config=types.ThinkingConfig(thinking_budget=-1),
    )

    output_text = ""
    for chunk in client.models.generate_content_stream(
        model=model_name,
        contents=contents,
        config=config,
    ):
        if chunk.text:
            output_text += chunk.text

    output_text = output_text.strip()

    # Attempt to auto-fix common JSON issues
    output_text = fix_json_string(output_text)

    try:
        prompts = json.loads(output_text)
        if not isinstance(prompts, list):
            raise ValueError("Generated output is not a list")
        return prompts
    except Exception as e:
        print(f" Failed to parse generated prompts: {e}")
        print(f" Raw output:\n{output_text}")
        return None
