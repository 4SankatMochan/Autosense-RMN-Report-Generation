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

"""
Descriptive Analysis ADK Agent that provides trend + LLM analysis + summary.
"""

from google.adk.agents import Agent
from .tools import analyze_trends, analyze_with_llm, summarize_single_prompt

descriptive_analysis_agent = Agent(
    name="descriptive_analysis_agent",
    instruction="Analyze trends in marketing data, generate LLM insights, and produce a summary.",
    tools=[analyze_trends, analyze_with_llm, summarize_single_prompt]
)
