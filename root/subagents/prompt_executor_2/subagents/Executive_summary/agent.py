import os

from google.adk.agents.llm_agent import LlmAgent
from .prompt import instruction_executive_summary
from .tools import executive_summary_agent
from google.adk.agents.callback_context import CallbackContext

def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""
    print("Calling Executive_summary subagent")

executive_summary_root_agent = LlmAgent(
    name="ExecutiveSummaryAgent",
    model=os.getenv("ROOT_AGENT_MODEL"),
    instruction=instruction_executive_summary(),
    description="Generate summary of the analyzed campaign data.",
    output_key="executive_summary_output",
    before_agent_callback=setup_before_agent_call,
    tools=[executive_summary_agent]
)

