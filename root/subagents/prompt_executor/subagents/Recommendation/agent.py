from google.adk.agents.llm_agent import LlmAgent
from .prompt import instruction_Recommendation
from .tools import recommendation_agent
from google.adk.agents.callback_context import CallbackContext

GEMINI_MODEL = "gemini-2.5-flash"

def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""
    print("Calling Recommendation subagent")

recommendation_root_agent = LlmAgent(
    name="RecommendationAgent",
    model=GEMINI_MODEL,
    instruction=instruction_Recommendation(),
    description="Generate actionable recommendations to improve campaign performance based on analyzed campaign data, comparisons, and observed insights.",
    output_key="recommendation_output",
    before_agent_callback=setup_before_agent_call,
    tools=[recommendation_agent]
)