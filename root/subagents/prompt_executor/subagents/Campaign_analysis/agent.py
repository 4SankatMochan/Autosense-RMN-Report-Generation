from google.adk.agents.llm_agent import LlmAgent
from .prompt import instruction_campaign_analysis
from .tools import campaign_analysis_agent
from google.adk.agents.callback_context import CallbackContext

GEMINI_MODEL = "gemini-2.5-flash"

def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""
    print("Calling campaign_analysis subagent")

campaign_analysis_root_agent = LlmAgent(
    name="CampaignAnalysisAgent",
    model=GEMINI_MODEL,
    instruction=instruction_campaign_analysis(),
    description="Analyzes aggregated campaign data and generates insights.",
    output_key="campaign_analysis_output",
    before_agent_callback=setup_before_agent_call,
    tools=[campaign_analysis_agent]
)

