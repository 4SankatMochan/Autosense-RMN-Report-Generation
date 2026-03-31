def return_instructions_root() -> str:

    instruction_prompt_root= """You need to call the tool `generate_prompt` tool
"""
    return instruction_prompt_root

########NEW#########
def return_instructions_root() -> str:
    instruction_prompt_root = """
You are a specialized Prompt Generator Agent. 
Your goal is to analyze the incoming user query, fuse it with persona and persona_report context 
(from the tool context state variables), and then call the tool `generate_prompt`.

When the user asks to generate a report:
1. Parse the user query to identify key elements such as persona, brand, platform, report type, date range, and KPIs.
2. Use the persona context {{persona}} to determine tone, focus_kpis, and communication style.
3. Use the persona_report context {{persona_report}} to extract report granularity, visualization preference, and output format.
4. Fuse all of these into a single long meta prompt (state["fused_prompt"]).
5. Then call the `generate_prompt` tool to create  requested number of structured prompts for the next stage (prompt_executor).
6. You have access to one tool: generate_prompt.
Call this tool exactly once per user query.
If it returns valid structured output, do not call it again.
Use its output directly as the final answer.

Always store your final list of prompts in `state["prompt_generator_out"]`.
"""
    return instruction_prompt_root

# **Important**: If the tool returns status = "missing_information",
# do not call the tool again.
# Ask the user clearly for the missing details.

def return_fusion_prompt() -> str:
    fusion_prompt_root_v1 = """You are acting as a prompt generator agent to assist {persona_name} in preparing prompts which will be useful while generating {report_type} (responses of these prompts addresses different sections of {report_type} through which downstreamm agents will create the report) 
    report for brand name {brand_name} and Campaign Id {campaign_id} if mentioned (otherwise ask user to give specific brand and campaign id or name to move forward), covering the {time_period} if given (otherwise analyze for all the period for which data is available).

    Campaign: {campaign_id}
    Report Type: {report_type}
    Time Period: {time_period}

    Focus KPIs: {focus_kpis}
    Granularity: {data_granularity}
    Tone: {persona_tone}

    Goal:
    Generate a list of independent prompts that will help retrieve insights for the following sections:

    • Context
    • Campaign Overview
    • Campaign-wise Analysis

    Rules:

    1. Prompts must look like natural user questions.
    2. Do not generate SQL.
    3. Prompts must be independent.
    4. Do not generate a prompt that requests the full report at once.  do not even mention anywhere in the prompts that these are for purpose of generating report.
    5. If campaign_id and brand_name are available , include them clearly (a must step).
    6. Unknown values should be written generically  so they can be replaced later.
    7. Generate multiple prompts for each section.
granularity
    Section requirements:

    Context
    Generate single prompts requesting campaign details including:
    Campaign ID, Campaign Name, Brand Name, Category, Media Types, Channel,
    Objective, Sub-Objective, Campaign Duration, Planned Spend, Actual Spend.

    Campaign Overview
    Generate multiple prompts requesting campaign overview tables including:
    Campaign ID, Campaign Name, Planned Spend, Campaign Objective,
    Total Ad Spend, Spend Utilization in one prompt  and KPI tables based on {focus_kpis} in another single prompt.

    Campaign-wise Analysis
    Generate prompts requesting analysis for each KPI in {focus_kpis[:4]} including:
    *trend analysis, *channel comparison, and *visualizations in one prompt.

    Must include in this section's prompts:
    1. Campaign and brand: {Campaign_id} and {brand_name}.
    2. Data granularity: {data_granularity} (Daily, Weekly)
    3. Campaign objective: {objective}
    4. Time Period: {time_period}}

    Ask for details of each KPI in separate prompt.
    For example :
        if the focus KPIs are ROAS, CTR, and Conversions,there should be one prompt for ROAS,one for CTR and one for Conversion . 

    Also generate single prompt asking for a concise campaign performance summary
    highlighting KPI performance, anomalies, and trends.

    Return JSON:

    {
    "Context": [],
    "Campaign Overview": [],
    "Campaign-wise Analysis": []
    }
    """

    fusion_prompt_root_v0 = f"""
    You are acting as a prompt generator agent to assist {persona_name} in preparing prompts which will be useful while generating {report_type} (responses of these prompts addresses different sections of {report_type} through which downstreamm agents will create the report) report for brand name {brand_name} and Campaign Id {campaign_phrase} if mentioned (otherwise ask user to give specific brand and campaign id or name to move forward), covering the {time_period} if given (otherwise analyze for all the period for which data is available).
    Generate a natural list of user prompts (not SQL) to help fill out the sections of the report mentioned below:
    Context, Campaign Overview, Campaign-wise Analysis.
    Below are the examples for some sections that you can use as a reference to generate the prompts for each section:
    1. Context:
        Campaign 1
        Campaign ID: CMP_2025_0001
        Campaign Name: Dove Nourishing Body Wash Launch
        Brand Name: Dove
        Category: Personal Care
        Media Type(s): Video, Shoppable Display, Social Ads
        Channel(s): Onsite, Offsite
        Objective: Conversion
        Sub-Objective: Drive Sales / Purchases, Add to Cart, Basket Building, Retarget PDP Viewers, Buy
        Box Wins
        Campaign Duration: 2025-05-01 – 2025-06-30
        Planned Spend: $50,000
        Actual Spend: $45,000 (latest date)
        Campaign 2
        Campaign ID: CMP_2025_0002
        Campaign Name: Dove Deodorant Awareness
        Brand Name: Dove
        Category: Personal Care
        Media Type(s): Video, CTV
        Channel(s): Channel-CTV
        Objective: Awareness
        Sub-Objective: Brand Awareness, Brand Recall, Video Views, Product Launch, Reach New
        Households, Category Awareness
        Campaign Duration: 2025-05-01 – 2025-06-30
        Planned Spend: $30,000
        Actual Spend: $28,000 (latest date)

        ** “In this section, ensure that a single prompt is generated for each campaign_id, and that the prompt explicitly asks for all of the following details: Campaign ID, Campaign Name, Brand Name, Category, Media Types, Channel, Objective, Sub‑Objective, Campaign Duration, Planned Spend, and Actual Spend(for latest date).”

    4. Campaign Overview:
        The prompt created for this section should be some thing similar to this-

        "This section provides an overview of the campaign, but the information can be summarized more clearly and efficiently using tables. Please try to generate prompts asking to include well‑structured tables for campaign overview.
        Start with a high‑level campaign summary table that includes (but is not limited to) the following columns:

        Campaign ID
        Campaign Name
        Planned Spend
        Campaign Objective (Awareness, Consideration, Conversion, Retention)
        Total Ad Spend
        Spend Utilization

        After creating the summary table, generate a tables for {focus_kpis} the specified objective {objective}. Ask in a single question and mention these details in the prompt:
        Ask for fetching KPIs based on its objective from relevant KPIs, also, since I have many data points based on date , write clear steps for getting a single relevant value for each KPI.
        The dataset contains multiple records across different dates and channels.
        Your goal is to compute a single consolidated KPI value per Channel for the campaign and brand.

        Follow these steps carefully.

        STEP 1 — Filter Data
        Filter the dataset using:

        Campaign ID

        Brand

        STEP 2 — Handle Multiple Dates
        Since multiple records exist across different dates, aggregate all rows belonging to the same Channel to produce a single value per KPI.

        Aggregation rules:

        Additive Metrics → SUM across all dates

        Ad_Spend

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

        Unique_Reach → take MAX or DISTINCT value for that channel.

        Derived Metrics (compute after aggregation; never average):

        CTR = Total_Clicks / Total_Impressions

        CPC = Total_Ad_Spend / Total_Clicks

        CPM = (Total_Ad_Spend / Total_Impressions) * 1000

        Frequency = Total_Impressions / Unique_Reach

        ROAS = Total_Campaign_Revenue / Total_Ad_Spend

        CPCV = Total_Ad_Spend / Completed_Views

        CVA = Conversions / Clicks

        Important rules:

        Never average CTR, CPC, ROAS, CPM, Frequency, or CVA.

        Always compute these metrics AFTER aggregation.

        STEP 3 — Create Campaign Summary Table
        Group the dataset by Channel and compute the aggregated KPI values using the rules above.

        STEP 4 — Generate Objective-Specific KPI Table

        Ensure the tables are clean, easy to understand, and formatted to provide a clear performance overview. Use consistent column naming conventions, align numeric values properly, and structure the tables to enable quick comparisons across campaigns and channels."

        ** Important **
        1. Split the prompts for this section so that different tables or sets of questions are generated through different prompts, for step by step functioning of LLM model and not complex fetching task at same time.
        2. Ensure that the prompts for this section are independent of each other, so that all dimensions of campaign overview are covered by different prompts and the LLM can focus on one aspect at a time while generating the report.
        3. For this section , donot forcefully ask all columns of tables mentioned above rather ask for the parameters if could be fetched from dataset available to create table from available columns only.

    5. Campaign-wise Analysis:
        This section provides a detailed analysis of campaign performance.
        This section requires some basic details of the campaign such as campaign name or campaign ad id or campaign duration etc mentioned in the user query or already fetched in previous cycle , so that the insights generated are specific to that campaign.
        The analysis should be for the specific Campaign {campaign_id} and Brand {brand_name}, focused on analysis using {focus_kpis[:4]} , {data_granularity} and Campaign Objective {objective} . Generate separate prompt for fetching proper insight through plots and graphs for each KPIs {focus_kpis[:3]}. 
        For example, if the focus KPIs are ROAS, CTR, and Conversions, the prompt for ROAS, CTR and Conversion sections should be separate and should also support creating visualizations like charts or graphs to illustrate performance trends over time, across channels, or by audience segments. 
        The analysis should also consider the data granularity (e.g., daily, weekly, monthly) to provide insights at the appropriate level of detail.
        Also, make a prompt to Generate a concise campaign performance summary for campaign objective as {objective} and funnel stage, highlighting key KPIs performances , anomaly (based on its objective), and summarizing overall and weekly performance trends using only the provided dataset.
        Points to be taken care while creating prompts for this section-
        ** Important ** 
        1. Make more than one prompts to support this section.
        2. The prompts should cover different aspects and should be as independent as possible to cover the section comprehensively.

    **Very Important**
    Keep the prompts created for one section as sublist under the section name, so that it is clear that these prompts are for generating content for this section.

    Tone: {persona_tone}.
    Focus KPIs: {', '.join(focus_kpis)}.
    Data granularity: {data_granularity}.
    Return only a JSON array of prompt strings.

    ** Important**: 
    1. If *campaign_id and *brand name is provided, include it in the prompts clearly(like for campaign id {campaign_id} and Brand name {brand_name}) to ensure insights are demanded specific to that campaign and brand. 
    2. Do not try to generate a prompt for generating all report at once, instead generate specific prompts for {','.join(report_sections)} to ensure depth and relevance of insights.
    3. Also, do not mention anywhere in the prompts that these are for purpose of generating report, instead make it look like a natural user query that a person would ask to get the insights related to campaign performance.
    4. Try to make sections as independent (except for executive summary or other summary and campaign comparison.) possible, so that the report covers most aspects of the campaign performance comprehensively.
    5. Since you don't have acess to the actual campaign data at this point, mention general terms( Do not mention examples on your own ) for unknown values like campaign duration or campaign objective in the prompts, so that when the actual data is fetched in next cycle, it can be easily replaced in the prompts to get specific insights.
    """
    return fusion_prompt_root_v1