# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
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
Tool for summarizing multiple descriptive insights into a single cohesive narrative.
"""

def summarize_insights(insights: list, llm, template: str) -> str:
    """
    Aggregates multiple descriptive insights into a cohesive narrative.

    Args:
        insights: List of individual insight summaries (strings).
        llm: LLM instance.
        template: Summarization prompt template.

    Returns:
        Final combined summary as a string.
    """
    combined_text = "\n".join(insights)
    filled_prompt = template.format(insights=combined_text)
    result = llm.generate_content(filled_prompt)
    return result.text
