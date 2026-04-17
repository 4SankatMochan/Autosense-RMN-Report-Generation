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
NL2SQL tools for generating SQL, running queries, and preprocessing data.
"""

import time
from google.cloud import bigquery
import asyncio

def generate_sql(nl_prompt: str) -> str:
    """
    Generate SQL query from a natural language prompt.
    """
    # TODO: Replace with actual LLM/NL2SQL logic
    sql_query = f"SELECT * FROM my_table WHERE condition LIKE '%{nl_prompt}%'"
    return sql_query


async def run_query(sql_query: str, project_id: str = None) -> dict:
    """
    Execute a SQL query on BigQuery and return the results.
    """
    client = bigquery.Client(project=project_id)
    try:
        query_job = client.query(sql_query)
        results = await asyncio.to_thread(query_job.result())

        rows = [dict(row.items()) for row in results]

        return {
            "query": sql_query,
            "data": rows,
        }

    except Exception as e:
        return {
            "query": sql_query,
            "error": str(e),
            "data": []
        }


def preprocess_data(query_result: dict) -> dict:
    """
    Preprocess the query results for downstream analysis.
    """
    data = query_result.get("data", [])
    row_count = len(data)

    summary = f"Retrieved {row_count} rows for further analysis."

    return {
        "summary": summary,
        "preprocessed_data": data,
    }
