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

"""Module for storing and retrieving agent instructions.

This module defines functions that return instruction prompts for the report_generator_agent.
These instructions guide the agent's behavior, workflow, and tool usage for converting
mixed content JSON data (text, charts, tables) into PDF reports.
"""


def return_instructions_report_generator() -> str:
    instruction_prompt_report_gen = """to generate a PDF, you MUST call the tool generate_pdf_report using a structured function call. Do NOT write Python code. Do NOT wrap it in print statements.
"""

    return instruction_prompt_report_gen