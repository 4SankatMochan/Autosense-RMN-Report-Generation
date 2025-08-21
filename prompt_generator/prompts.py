SQL_PROMPT_TEMPLATE = """
Write a BigQuery SQL query to analyze the following request:
"{query}"
Query must read from the table `acn-cda.RMN_Campaign_Data_AgentTest.campaign_performance_metrics`
Ensure the query includes dimensions like `date`, KPIs like CTR, Spend, and filters if mentioned.
"""

INSIGHT_PROMPT_TEMPLATE = """
Given the following dataset trends:
{trend_output}
Generate a marketing-friendly business narrative describing key insights.
"""

SUMMARY_PROMPT_TEMPLATE = """
Summarize these insights across {num_prompts} prompts into a cohesive business narrative.
Write in simple, non-technical language suitable for a marketing team.
"""