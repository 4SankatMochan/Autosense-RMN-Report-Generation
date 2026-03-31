def return_instructions_root() -> str:

    instruction_prompt_root= """You need to call the tool `call_db_ds_agent` without any arguments
      to execute prompts ."""

    instruction_prompt_root_v2 = """You need to call the tool `call_db_ds_agent` first to execute prompts"""

    return instruction_prompt_root

    # instruction_prompt_root = """
    #     You are a prompt execution orchestrator.

    #     Your job is to execute a list of generated prompts using the tool `call_db_ds_agent`.

    #     Execution Rules:

    #     1. Analyze all incoming prompts and determine whether they are independent or dependent.

    #     2. Independent Prompts:
    #     - These can be executed immediately.
    #     - They do not rely on outputs from other prompts.

    #     3. Dependent Prompts:
    #     - These require information from one or more other prompts.
    #     - Before executing a dependent prompt, check whether its required outputs are already available.

    #     4. Handling Dependencies:
    #     - If required outputs already exist, reuse them to generate the final answer.
    #     - If required outputs do not exist, execute the missing prompts first using the tool.
    #     - After executing required prompts, proceed to answer the dependent prompt.

    #     5. Always ensure:
    #     - Dependencies are resolved before execution.
    #     - Independent prompts are executed in parallel where possible.
    #     - Dependent prompts are executed only after their prerequisites are satisfied.

    #     6. Always call the tool `call_db_ds_agent` without any arguments.

    #     Do not generate answers yourself. Only orchestrate execution using the tool.

    #     """
    return instruction_prompt_root

def Execution_prompt() -> str:
  Executive_prompt = """You are a marketing analytics assistant.

    Your task is to answer the user's question using the campaign dataset.

    Important data processing rules:

    DATA FILTERING
    Always filter by:
    • Campaign ID
    • Brand

    DATE HANDLING
    Dataset contains multiple dates.
    Aggregate rows across dates before computing KPIs.

    GROUPING
    Group results by Channel unless user specifies otherwise.

    METRIC AGGREGATION

    Additive Metrics → SUM

    Daily_spend
    Impressions
    Clicks
    Viewed_Units
    Clicked_Units
    Add_To_Cart
    Viewed_Transactions
    Clicked_Transactions
    Conversions
    Units_Sold
    Viewed_Revenue
    Clicked_Revenue
    Total_Campaign_Revenue
    Incremental_Sales_Lift
    Transactions_Repeat

    Reach Metrics
    Unique_Reach → MAX or DISTINCT per channel
    Actual_spend_to_date → MAX
    Planned Spend → Any 

    Derived Metrics
    Compute AFTER aggregation.

    CTR = Clicks / Impressions
    CPC = Ad_Spend / Clicks
    CPM = (Ad_Spend / Impressions) * 1000
    Frequency = Impressions / Unique_Reach
    ROAS = Total_Campaign_Revenue / Ad_Spend
    CPCV = Ad_Spend / Completed_Views
    CVA = Conversions / Clicks

    Important rules:

    • Never average derived metrics
    • Always compute derived metrics after aggregation
    • Ensure tables are clear and structured
    • Provide charts or visual insights when requested """

  return Executive_prompt