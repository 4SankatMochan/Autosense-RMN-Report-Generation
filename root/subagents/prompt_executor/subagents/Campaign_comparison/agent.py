from google.adk.agents.llm_agent import LlmAgent
from .prompt import instruction_Campaign_comparison
from .tools import campaign_comparison_agent
from google.adk.agents.callback_context import CallbackContext

GEMINI_MODEL = "gemini-2.5-flash"

def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""
    print("Calling Campaign_comparison subagent")

campaign_comparison_root_agent = LlmAgent(
    name="CampaignComparisonAgent",
    model=GEMINI_MODEL,
    instruction=instruction_Campaign_comparison(),
    description="Compare performance across multiple campaigns, segments, or time periods and highlight key differences, trends, and relative performance insights.",
    output_key="campaign_comparison_output",
    before_agent_callback=setup_before_agent_call,
    tools=[campaign_comparison_agent]
)