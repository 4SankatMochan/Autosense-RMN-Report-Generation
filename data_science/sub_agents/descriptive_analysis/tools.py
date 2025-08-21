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
Descriptive analysis tools: trend analysis, LLM analysis, summarization.
"""

def analyze_trends(df) -> str:
    """
    Analyze trends from the dataframe.

    Args:
        df: Pandas DataFrame containing marketing KPIs.

    Returns:
        A string summary of trends.
    """
    trends = []
    for col in ['CTR', 'Spend', 'Impressions']:
        if col not in df.columns:
            continue
        diff = df[col].diff().mean()
        if diff > 0:
            trends.append(f"{col} is increasing.")
        elif diff < 0:
            trends.append(f"{col} is decreasing.")
        else:
            trends.append(f"{col} is stable.")
    return "\n".join(trends)


def analyze_with_llm(df, llm) -> str:
    """
    Use LLM to analyze the data and generate insights.

    Args:
        df: Pandas DataFrame.
        llm: LLM instance.

    Returns:
        LLM-generated insight text.
    """
    prompt = f"Analyze the following marketing data:\n{df.head(5).to_markdown()}\nGenerate meaningful insights."
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def summarize_single_prompt(insight_text: str, llm) -> str:
    """
    Summarizes the insight from a single prompt using the LLM.

    Args:
        insight_text: Combined trend + LLM narrative for a single prompt.
        llm: LLM instance.

    Returns:
        A clean, business-friendly summary.
    """
    prompt = f"Summarize the following insight in clear business language:\n{insight_text}"
    result = llm.generate_content(prompt)
    return result.text
