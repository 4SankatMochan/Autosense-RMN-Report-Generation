import os
import json


def return_campaign_logic_prompt() -> str:
    """Load curated campaign logic prompt from markdown file."""
    base_dir = os.path.dirname(__file__)
    md_path = os.path.join(base_dir, "campaign_logic_prompt.md")

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "# WARNING: campaign_logic_prompt.md not found – minimal logic rules loaded."


def load_data_dictionary() -> dict:
    """Load JSON schema (data_dictionary.json) from same folder."""
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, "data_dictionary.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "error": "data_dictionary.json not found",
            "tables": [],
            "relationships": []
        }


DATA_DICTIONARY = load_data_dictionary()


def return_instructions_bigquery() -> str:
    """
    Return final instruction string for BigQuery agent.
    Includes:
    1. BigQuery orchestration prompt (tools + output rules)
    2. Curated campaign logic prompt (markdown)
    3. Full schema and business rules (JSON from data_dictionary.json)
    """

    # Tool selection based on environment variable
    NL2SQL_METHOD = os.getenv("NL2SQL_METHOD", "BASELINE")
    if NL2SQL_METHOD in ["BASELINE", "CHASE"]:
        db_tool_name = "initial_bq_nl2sql"
    else:
        raise ValueError(f"Unknown NL2SQL method: {NL2SQL_METHOD}")

    schema_text = json.dumps(DATA_DICTIONARY, indent=2)
    campaign_prompt = return_campaign_logic_prompt()

    # Explicit orchestration rules
    orchestration_rules = f"""
## Orchestration Instructions
1. Always use `{db_tool_name}` to generate initial SQL from the natural language question.
2. Always use `run_bigquery_validation` to validate the SQL for syntax and function errors.
3. Final output MUST be returned in JSON format with four keys:
   - "explain": A step-by-step reasoning of how SQL was generated
   - "sql": The final validated SQL string
   - "sql_results": Raw results from the executed SQL
   - "nl_results": Natural language summary of the results for the user
4. When the user requests week-on-week or week or  quarter-on-quarter or quarter data:
      - Detect whether it's a week or quarter-based query.
      - Aggregate metrics (e.g. SUM, AVG, COUNT) by week or quarter.
      - For week-on-week:
          * Assign continuous week numbers from the start of the date range.
      - For quarter-on-quarter:
          * Use quarter number from the date.
      - Sort results by week or quarter number.
"""

    # Tool usage enforcement
    tool_usage_rules = f"""
## Tool Usage Rules
- You MUST call `{db_tool_name}` to generate SQL.
- You MUST call `run_bigquery_validation` after generating SQL.
- Do NOT invent SQL directly. Always use tools.
"""

    # Schema usage priority
    schema_usage_rules = """
## Schema Usage Rules
- Always prefer live BigQuery schema for field names and data types.
- Always cross-check with data_dictionary.json for:
  - Enum values (media_type, channels, objectives, etc.)
  - Relationships (campaign ↔ performance, clickstream ↔ transactions, etc.)
  - Field descriptions and business semantics
- If there is any mismatch:
  - Trust BigQuery schema for field names & datatypes
  - Trust data_dictionary.json for relationships, enums, and business definitions
"""

    # Validation checklist reinforcement
    validation_checklist = """
## Validation Checklist
- Did I use only fields from BigQuery schema or data_dictionary.json?
- Did I apply ROAS/CTR/CPC/CVR rules correctly from campaign logic prompt?
- Did I clamp metrics to valid ranges (when enrichment logic applies)?
- Did I include helpful comments in SQL?
- Did I apply date filters when relevant?
"""

    # Final instruction string
    instruction_prompt_bqml_v1 = f"""
# BigQuery Orchestration Prompt
You are an AI assistant serving as a SQL orchestrator for BigQuery.
Your role: Convert natural language → SQL using tools, schema, and campaign logic.

{orchestration_rules}

{tool_usage_rules}

---

# Curated Campaign Logic Prompt
{campaign_prompt}

---

# Schema Usage Rules
{schema_usage_rules}

---

# Full Schema & Business Rules
Below is the complete schema and business rules (from data_dictionary.json).
Use this alongside live BigQuery schema as the source of truth:

{schema_text}

---

# Validation Checklist
{validation_checklist}
"""
    return instruction_prompt_bqml_v1
