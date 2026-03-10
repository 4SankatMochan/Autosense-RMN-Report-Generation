# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This project uses ReportLab (BSD License) for PDF generation.
# ReportLab: https://www.reportlab.com/
# ReportLab License: https://www.reportlab.com/software/opensource/
# Specifically uses: ReportLab PDF Toolkit (Open Source) and json2pdf scaffolding.

"""PDF Generator Agent: Converts structured JSON data (containing text, charts, tables) into PDF reports."""
# import agent, tools, import return fun from the prompt, import the function from tools.py
import os
from google.adk.agents import Agent
# from report_generation.sub_agents.pdf_generator import tools # Import the tools module containing the function
from .prompts import return_instructions_report_generator 
from .tools import generate_pdf_report
from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext

#     # model = GenerativeModel(os.getenv("SEQUENTIAL_AGENT"))
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

root_agent = Agent(
    model=os.getenv("PDF_GENERATOR_AGENT_MODEL"),
    description= "PDF Generator Agent Converts structured JSON data into PDF reports.",
    name="pdf_generator_agent",
    instruction=return_instructions_report_generator(),
    tools=[generate_pdf_report] # Reference the function from tools.py
)