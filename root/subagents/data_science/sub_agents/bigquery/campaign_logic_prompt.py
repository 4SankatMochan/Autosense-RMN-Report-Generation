import os

def return_campaign_logic_prompt() -> str:
    """Load curated campaign logic prompt from markdown file."""
    base_dir = os.path.dirname(__file__)
    md_path = os.path.join(base_dir, "campaign_logic_prompt.md")

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "# ERROR: campaign_logic_prompt.md not found"
