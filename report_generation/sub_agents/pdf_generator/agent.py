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
from report_generation.sub_agents.pdf_generator import tools # Import the tools module containing the function
from report_generation.sub_agents.pdf_generator.prompts import return_instructions_report_generator 
from report_generation.sub_agents.pdf_generator.tools import generate_report

root_agent = Agent(
    model=os.getenv("PDF_GENERATOR_AGENT_MODEL"),
    description= "PDF Generator Agent Converts structured JSON data into PDF reports.",
    name="pdf_generator_agent",
    instruction=return_instructions_report_generator(),
    tools=[generate_report], # Reference the function from tools.py
)