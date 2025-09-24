# import os
# from data_science.sub_agents.bigquery.prompts import return_instructions_bigquery
# from data_science.sub_agents.bigquery.campaign_logic_prompt import return_campaign_logic_prompt

# # Path variables
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PROMPT_DIR = os.path.join(BASE_DIR, "data_science", "sub_agents", "bigquery")
# CAMPAIGN_MD_PATH = os.path.join(PROMPT_DIR, "campaign_logic_prompt.md")
# DATA_DICT_PATH = os.path.join(PROMPT_DIR, "data_dictionary.json")


# def main():
#     print("🔍 Checking Prompt Loading...\n")

#     # Load final instructions
#     prompt = return_instructions_bigquery()

#     print("✅ Prompt loaded successfully!\n")

#     # Confirm parts
#     print("Contains Orchestration Instructions:", "SQL expert for BigQuery" in prompt)
#     print("Contains Curated Campaign Logic:", "# Curated Campaign Logic Prompt" in prompt)
#     print("Contains JSON Schema:", "# Full Schema & Business Rules" in prompt)

#     # Show file locations being used
#     print("\n📂 File Locations:")
#     print(f"Campaign Logic Prompt Path: {CAMPAIGN_MD_PATH} (Exists: {os.path.exists(CAMPAIGN_MD_PATH)})")
#     print(f"Data Dictionary Path:       {DATA_DICT_PATH} (Exists: {os.path.exists(DATA_DICT_PATH)})")

#     # Preview campaign logic file directly
#     try:
#         with open(CAMPAIGN_MD_PATH, "r", encoding="utf-8") as f:
#             campaign_preview = f.read().splitlines()[:10]
#         print("\n--- Campaign Logic Prompt Preview (first 10 lines) ---")
#         for i, line in enumerate(campaign_preview, 1):
#             print(f"{i:02}: {line}")
#     except FileNotFoundError:
#         print("\n❌ Campaign Logic Prompt file not found!")

#     # Preview full prompt (cut to 100 lines for readability)
#     print("\n--- Final Combined Prompt Preview (first 100 lines) ---")
#     for i, line in enumerate(prompt.splitlines()[:100], 1):
#         print(f"{i:02}: {line}")


# if __name__ == "__main__":
#     main()


import os
from data_science.sub_agents.bigquery.prompts import (
    return_instructions_bigquery,
    return_campaign_logic_prompt,
    load_data_dictionary,
)

def main():
    prompt = return_instructions_bigquery()

    print("✅ Prompt loaded successfully!\n")

    # Resolve absolute paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(base_dir, "campaign_logic_prompt.md")
    json_path = os.path.join(base_dir, "data_dictionary.json")

    print("📂 File Locations:")
    print(f"Campaign Logic Prompt Path: {os.path.abspath(md_path)} (Exists: {os.path.exists(md_path)})")
    print(f"Data Dictionary Path:       {os.path.abspath(json_path)} (Exists: {os.path.exists(json_path)})")

    # Check contents
    print("\n🔍 Sanity Checks:")
    print("Contains Orchestration Instructions:", "SQL expert for BigQuery" in prompt)
    print("Contains Curated Campaign Logic:", "# Curated Campaign Logic Prompt" in prompt)
    print("Contains JSON Schema:", "# Full Schema & Business Rules" in prompt)

    # Show preview
    print("\n--- Final Combined Prompt Preview (first 50 lines) ---")
    for i, line in enumerate(prompt.splitlines()[:50], start=1):
        print(f"{i:02}: {line}")

if __name__ == "__main__":
    main()
