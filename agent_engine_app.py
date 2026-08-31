from vertexai.preview.reasoning_engines import AdkApp

from root.agent import root_agent

adk_app = AdkApp(
    agent=root_agent,
    enable_tracing=False,
)