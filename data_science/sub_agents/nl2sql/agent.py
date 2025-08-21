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
NL2SQL agent that generates SQL, runs BigQuery query, and preprocesses results.
"""

from google.adk.agents import Agent
from .tools import generate_sql, run_query, preprocess_data

nl2sql_agent = Agent(
    name="nl2sql_agent",
    instruction="Generate SQL from natural language prompt, run query, and preprocess data.",
    tools=[generate_sql, run_query, preprocess_data]
)
