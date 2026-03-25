"""Data Visualiztion Agent V1: generate simple plots using tools."""
import os
from google.adk.agents import SequentialAgent
from .sub_agents.text_viz_json_agent.agent import root_agent as text_viz_json_agent
from .sub_agents.report_summarizer.agent import root_agent as text_viz_report_summarizer_agent
from .sub_agents.pdf_generator.agent import root_agent as pdf_generator_agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from google.genai import types
from vertexai.preview.generative_models import GenerativeModel

def setup_before_agent_call(callback_context: CallbackContext):
    callback_context.state["persona_context"] = """
"""
    # callback_context.state["session_id"] = callback_context._invocation_context.session.id
    print(f"inside report gen seq agent: session id from invocation context {callback_context._invocation_context.session.id}")
    callback_context.state["session_id"] = callback_context._invocation_context.session.id
    callback_context.state["user_id"] = callback_context._invocation_context.user_id
    print(f"inside report gen seq agent: session id from state {callback_context.state["session_id"]}")
    # model = GenerativeModel(os.getenv("SEQUENTIAL_AGENT"))
    # query = callback_context.user_content.parts[0].text
    # prompt = f"""
    #             You are a binary classifier. Your job is to determine whether a user query is requesting a report to be generated from the *current session data*.
    #             Return only one of two values: `True` or `False`.
    #             Respond `True` **only** if the user is asking to generate a report (in any wording) from the *current session*, *this conversation*, or *recent interaction*. It can include phrases like "regenerate report", "create report from this session", "generate summary of our current session", etc.
    #             In all other cases, return `False`.
    #             ### Examples:
    #             User: "Regenerate report from current session"  
    #             Output: True
    #             User: "Can you generate a summary of what we've discussed so far?"  
    #             Output: True
    #             User: "Make a report using this session's data"  
    #             Output: True
    #             User: "Create a new report using uploaded file"  
    #             Output: False
    #             User: "Generate monthly sales report for August"  
    #             Output: False
    #             User: "Summarize the uploaded CSV file"  
    #             Output: False
    #             User: "Give me a quick overview of our current chat"  
    #             Output: True
    #             User: "Please create a new report based on the CRM export"  
    #             Output: False
    #             User: "Draft a report using this conversation"  
    #             Output: True
    #             User: "Send the latest report from the database"  
    #             Output: False
    #             User: "Generate bar chart/report showing ... "
    #             Output : False
    #             Now classify the following user input:
    #             # User: {query}

    #             Output:


    # """
    # response = model.generate_content(
    #         prompt,
    #     generation_config={
    #         "temperature": 0.01,
    #     })
    # with open("debug_log.txt", "a") as f:
    #     f.write(f"user query :{query} \n")
    #     # f.write(f"response from report generator: {response}\n")
    #     f.write(f"{response.candidates[0].content.parts[0].text.strip()}")
    # res = response.candidates[0].content.parts[0].text.strip()
    # if res.lower()=='true':
    #     return None
    # else:
    #     return types.Content(
    #         role="model",
    #         parts=[types.Part(text="I’m sorry, but your request doesn't appear to be about generating a session report. Agent not triggered.")]
    #     )

root_agent = SequentialAgent(
    description= "Sequential Report Generation Agent",
    name="report_generation_agent",
    sub_agents = [text_viz_json_agent,text_viz_report_summarizer_agent,pdf_generator_agent],
    before_agent_callback=setup_before_agent_call,
)

    # before_agent_callback=setup_before_agent_call,