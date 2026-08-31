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
    return (
        "Call the tool generate_pdf_report (no arguments needed) to generate the PDF report. "
        "After the tool returns, relay its COMPLETE response to the user VERBATIM — do not summarise, "
        "do not omit any lines, do not paraphrase. The tool response includes the download URL, "
        "all chart links, timing information, and the GCS path. Output it exactly as returned."
    )