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

"""This file contains the tools used by the database agent."""

import datetime
import logging
import os
import re
import pandas as pd
import asyncio
from root.subagents.data_science.utils.utils import get_env_var
from google.adk.tools import ToolContext
from google.cloud import bigquery
from google.genai import Client

from .chase_sql import chase_constants

from google.cloud import bigquery
import pandas as pd
import datetime

# Assume that `BQ_PROJECT_ID` is set in the environment. See the
# `data_agent` README for more details.
project = os.getenv("BQ_PROJECT_ID", None)
location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
llm_client = Client(vertexai=True, project=project, location=location)

MAX_NUM_ROWS = 500 # 80 to 500 by Krishna on 5-Sept-2025


database_settings = None
bq_client = None


def get_bq_client():
    """Get BigQuery client."""
    global bq_client
    if bq_client is None:
        bq_client = bigquery.Client(project=get_env_var("BQ_PROJECT_ID"))
    return bq_client


async def get_database_settings():
    """Get database settings."""
    global database_settings
    if database_settings is None:
        database_settings = await update_database_settings()
    print('dbs:',database_settings)
    return database_settings


async def update_database_settings():
    """Update database settings."""
    global database_settings
    ddl_schema = await get_bigquery_schema(
        get_env_var("BQ_DATASET_ID"),
        client=get_bq_client(),
        project_id=get_env_var("BQ_PROJECT_ID"),
    )
    database_settings = {
        "bq_project_id": get_env_var("BQ_PROJECT_ID"),
        "bq_dataset_id": get_env_var("BQ_DATASET_ID"),
        "bq_ddl_schema": ddl_schema,
        # Include ChaseSQL-specific constants.
        **chase_constants.chase_sql_constants_dict,
    }
    print('dbs',database_settings)
    return database_settings

from google.cloud import bigquery
import pandas as pd
import datetime

async def get_bigquery_schema(dataset_id, client=None, project_id=None, max_example_rows=5):
    """
    Returns schema + DDL + example rows for:
      - All tables if dataset contains tables
      - The materialized view if dataset contains an MV
    """
    if client is None:
        client = bigquery.Client(project=project_id)

    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    ddl_statements = ""

    # Get all table-like objects in the dataset
    tables_objs = [client.get_table(dataset_ref.table(t.table_id)) for t in client.list_tables(dataset_ref)]

    # Separate base tables and materialized views
    base_tables = [t for t in tables_objs if t.table_type == "TABLE"]
    mvs = [t for t in tables_objs if t.table_type == "MATERIALIZED_VIEW"]

    # If dataset has base tables
    if base_tables:
        for table_obj in base_tables:
            table_ref = table_obj.reference
            ddl_statement = f"CREATE OR REPLACE TABLE `{table_ref}` (\n"
            for field in table_obj.schema:
                ddl_statement += f"  `{field.name}` {field.field_type}"
                if field.mode == "REPEATED":
                    ddl_statement += " ARRAY"
                if field.description:
                    ddl_statement += f" COMMENT '{field.description.replace('\'','\'\'')}'"
                ddl_statement += ",\n"
            ddl_statement = ddl_statement[:-2] + "\n);\n\n" if table_obj.schema else ddl_statement[:-2] + "\n);\n\n"

            # Example rows
            rows = client.list_rows(table_ref, max_results=max_example_rows).to_dataframe()
            if not rows.empty:
                ddl_statement += f"-- Example values for table `{table_ref}`:\n"
                for _, row in rows.iterrows():
                    row_str = "("
                    for val in row.values:
                        if pd.isna(val):
                            row_str += "NULL,"
                        elif isinstance(val, str):
                            row_str += f"'{val.replace('\'','\'\'')}',"
                        elif isinstance(val, (datetime.date, datetime.datetime)):
                            row_str += f"'{val.isoformat()}',"
                        elif isinstance(val, bool):
                            row_str += "TRUE," if val else "FALSE,"
                        else:
                            row_str += str(val) + ","
                    row_str = row_str[:-1] + ");\n\n"
                    ddl_statement += f"INSERT INTO `{table_ref}` VALUES\n" + row_str

            ddl_statements += ddl_statement
        return ddl_statements

    # If dataset has an MV
    elif mvs:
        table_obj = mvs[0]  # Assuming only one MV per dataset
        table_ref = table_obj.reference
        fq_name = f"{table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}"

        # 1) Schema block
        ddl_statement = f"CREATE OR REPLACE TABLE `{fq_name}` (\n"
        for field in table_obj.schema:
            ddl_statement += f"  `{field.name}` {field.field_type}"
            if field.mode == "REPEATED":
                ddl_statement += " ARRAY"
            if field.description:
                desc = field.description.replace("'", "''")
                ddl_statement += f" COMMENT '{desc}'"
            ddl_statement += ",\n"
        ddl_statement = ddl_statement[:-2] + "\n);\n\n" if table_obj.schema else ddl_statement[:-2] + "\n);\n\n"

        # 2) Materialized view DDL
        view_query = getattr(table_obj, "view_query", None) or f"SELECT * FROM `{fq_name}` LIMIT 0"
        ddl_statement += f"CREATE OR REPLACE MATERIALIZED VIEW `{fq_name}` AS\n{view_query};\n\n"

        # 3) Example rows
        try:
            job = client.query(f"SELECT * FROM `{fq_name}` LIMIT {max_example_rows}")
            df = await asyncio.to_thread(job.result)
            df=df.to_dataframe()
            if not df.empty:
                ddl_statement += f"-- Example rows for materialized view `{fq_name}`:\n"
                for _, row in df.iterrows():
                    parts = []
                    for val in row.values:
                        if pd.isna(val):
                            parts.append("NULL")
                        elif isinstance(val, str):
                            parts.append(f"'{val.replace('\'','\'\'')}'")
                        elif isinstance(val, (datetime.date, datetime.datetime)):
                            parts.append(f"'{val.isoformat()}'")
                        elif isinstance(val, bool):
                            parts.append("TRUE" if val else "FALSE")
                        else:
                            parts.append(str(val))
                    ddl_statement += "SELECT " + ", ".join(parts) + ";\n"
                ddl_statement += "\n"
        except Exception as e:
            ddl_statement += f"-- Unable to fetch example rows: {e}\n\n"

        ddl_statements += ddl_statement
        return ddl_statements

    # If dataset is empty
    else:
        return "-- No tables or materialized views found in dataset.\n"


def initial_bq_nl2sql(
    question: str,
    tool_context: ToolContext,
) -> str:
    """Generates an initial SQL query from a natural language question.

    Args:
        question (str): Natural language question.
        tool_context (ToolContext): The tool context to use for generating the SQL
          query.

    Returns:
        str: An SQL statement to answer this question.
    """

    prompt_template = """
You are a BigQuery SQL expert tasked with answering user's questions about BigQuery tables by generating SQL queries in the GoogleSql dialect.  Your task is to write a Bigquery SQL query that answers the following question while using the provided context.

**Guidelines:**

- **Table Referencing:** Always use the full table name with the database prefix in the SQL statement.  Tables should be referred to using a fully qualified name with enclosed in backticks (`) e.g. `project_name.dataset_name.table_name`.  Table names are case sensitive.
- **Joins:** Join as few tables as possible. When joining tables, ensure all join columns are the same data type. Analyze the database and the table schema provided to understand the relationships between columns and tables.
- **Aggregations:**  Use all non-aggregated columns from the `SELECT` statement in the `GROUP BY` clause.
- **SQL Syntax:** Return syntactically and semantically correct SQL for BigQuery with proper relation mapping (i.e., project_id, owner, table, and column relation). Use SQL `AS` statement to assign a new name temporarily to a table column or even a table wherever needed. Always enclose subqueries and union queries in parentheses.
- **Column Usage:** Use *ONLY* the column names (column_name) mentioned in the Table Schema. Do *NOT* use any other column names. Associate `column_name` mentioned in the Table Schema only to the `table_name` specified under Table Schema.
- **FILTERS:** You should write query effectively  to reduce and minimize the total rows to be returned. For example, you can use filters (like `WHERE`, `HAVING`, etc. (like 'COUNT', 'SUM', etc.) in the SQL query.
- **LIMIT ROWS:**  The maximum number of rows returned should be less than {MAX_NUM_ROWS}.
- **Values with apostrophe:** If a value contains an apostrophe ('), wrap the value in double quotes (" ") instead of single quotes in the SQL query.

**Schema:**

The database structure is defined by the following table schemas (possibly with sample rows):

```
{SCHEMA}
```

**Natural language question:**

```
{QUESTION}
```

**Think Step-by-Step:** Carefully consider the schema, question, guidelines, and best practices outlined above to generate the correct BigQuery SQL.

   """
    tool_context.state["tool_called"] = "tools py initial_bq_nl2sql"
    ddl_schema = tool_context.state["database_settings"]["bq_ddl_schema"]

    prompt = prompt_template.format(
        MAX_NUM_ROWS=MAX_NUM_ROWS, SCHEMA=ddl_schema, QUESTION=question
    )
    # config={"temperature": 0.1}
    config={"temperature": 0.01}
    response = llm_client.models.generate_content(
        model=os.getenv("BASELINE_NL2SQL_MODEL"),
        contents=prompt,
        config=config,
    )
    tool_context.state["config_used"]=config
    sql = response.text
    if sql:
        sql = sql.replace("```sql", "").replace("```", "").strip()

    print("\n sql:", sql)

    tool_context.state["sql_query"] = sql
    
    return sql


def run_bigquery_validation(
    sql_string: str,
    tool_context: ToolContext,
) -> str:
    """Validates BigQuery SQL syntax and functionality.

    This function validates the provided SQL string by attempting to execute it
    against BigQuery in dry-run mode. It performs the following checks:

    1. **SQL Cleanup:**  Preprocesses the SQL string using a `cleanup_sql`
    function
    2. **DML/DDL Restriction:**  Rejects any SQL queries containing DML or DDL
       statements (e.g., UPDATE, DELETE, INSERT, CREATE, ALTER) to ensure
       read-only operations.
    3. **Syntax and Execution:** Sends the cleaned SQL to BigQuery for validation.
       If the query is syntactically correct and executable, it retrieves the
       results.
    4. **Result Analysis:**  Checks if the query produced any results. If so, it
       formats the first few rows of the result set for inspection.

    Args:
        sql_string (str): The SQL query string to validate.
        tool_context (ToolContext): The tool context to use for validation.

    Returns:
        str: A message indicating the validation outcome. This includes:
             - "Valid SQL. Results: ..." if the query is valid and returns data.
             - "Valid SQL. Query executed successfully (no results)." if the query
                is valid but returns no data.
             - "Invalid SQL: ..." if the query is invalid, along with the error
                message from BigQuery.
    """

    def cleanup_sql(sql_string):
        """Processes the SQL string to get a printable, valid SQL string."""

        # 1. Remove backslashes escaping double quotes
        sql_string = sql_string.replace('\\"', '"')

        # 2. Remove backslashes before newlines (the key fix for this issue)
        sql_string = sql_string.replace("\\\n", "\n")  # Corrected regex

        # 3. Replace escaped single quotes
        sql_string = sql_string.replace("\\'", "'")

        # 4. Replace escaped newlines (those not preceded by a backslash)
        sql_string = sql_string.replace("\\n", "\n")

        # 5. Add limit clause if not present
        if "limit" not in sql_string.lower():
            sql_string = sql_string + " limit " + str(MAX_NUM_ROWS)

        return sql_string

    logging.info("Validating SQL: %s", sql_string)
    sql_string = cleanup_sql(sql_string)
    logging.info("Validating SQL (after cleanup): %s", sql_string)

    final_result = {"query_result": None, "error_message": None}

    # More restrictive check for BigQuery - disallow DML and DDL
    if re.search(
        r"(?i)(update|delete|drop|insert|create|alter|truncate|merge)", sql_string
    ):
        final_result["error_message"] = (
            "Invalid SQL: Contains disallowed DML/DDL operations."
        )
        return final_result

    try:
        query_job = get_bq_client().query(sql_string)
        results = query_job.result()  # Get the query results

        if results.schema:  # Check if query returned data
            rows = [
                {
                    key: (
                        value
                        if not isinstance(value, datetime.date)
                        else value.strftime("%Y-%m-%d")
                    )
                    for (key, value) in row.items()
                }
                for row in results
            ][
                :MAX_NUM_ROWS
            ]  # Convert BigQuery RowIterator to list of dicts
            # return f"Valid SQL. Results: {rows}"
            final_result["query_result"] = rows

            tool_context.state["query_result"] = rows

        else:
            final_result["error_message"] = (
                "Valid SQL. Query executed successfully (no results)."
            )

    except (
        Exception
    ) as e:  # Catch generic exceptions from BigQuery  # pylint: disable=broad-exception-caught
        final_result["error_message"] = f"Invalid SQL: {e}"

    print("\n run_bigquery_validation final_result: \n", final_result)

    return final_result
