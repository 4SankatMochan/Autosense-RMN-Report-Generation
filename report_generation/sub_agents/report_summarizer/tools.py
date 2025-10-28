from google import genai
from google.genai import types
import os
from .prompts import generate_report_prompt, format_report_prompt
from typing import List, Optional
from google.adk.tools import ToolContext
from vertexai.preview.generative_models import GenerativeModel
import json

# template = """# [Report Title]

# ## 1. Executive Summary
# ## 2. Introduction
# ### 2.1. Background
# ### 2.2. Report Objectives
# ## 3. Channel Performance Overview
# ### 3.1. Distinct Channels Identified
# ### 3.2. Total Attributed Sales by Channel
# ## 4. Daily Performance Analysis
# ### 4.1. Daily Attributed Sales Value
# ## 5. Conclusion and Recommendations
# """
# context = """This report is prepared for the Marketing and Sales leadership team to provide a comprehensive overview of campaign performance across different channels. The primary objective is to understand which channels contribute most effectively to attributed sales and to identify overall daily sales patterns. The insights derived from this analysis will be crucial in informing strategic decisions related to optimizing future marketing spend, resource allocation, and campaign targeting to maximize ROI.
# """
# filters = """nil
# """
######## TESTING PURPOSES ONLY ########
report_template = """
{
  "Campaign_Performance_Report": {
    "1.Context": {
      "Campaigns": [
        {
          "Campaign_ID": "",
          "Campaign_Name": "",
          "Brand_Name": "",
          "Category": "",
          "Media_Types": [],
          "Channels": [],
          "Objective": "",
          "Sub_Objective": [],
          "Campaign_Manager": "",
          "Campaign_Duration": {
            "Start_Date": "",
            "End_Date": ""
          },
          "Planned_Budget": "",
          "Actual_Spend": ""
        }
      ]
    },
    "2.Customization_Options": {
      "Timeline": ["Full campaign period", "Weekly report view", "Daily report view"],
      "By_Creative": ["App", "Channel-CTV", "Onsite", "Offsite", "Instore"]
    },
    "3.Executive_Summary": {
      "Overview": "",
      "Overall_Performance": "",
      "Channel_Format_Performance": "",
      "Optimization_Insight": ""
    },
    "4.Campaign_Overview": {
      "Campaign_Summary_Table": [
        {
          "Start_Date": "",
          "End_Date": "",
          "Campaign_ID": "",
          "Campaign_Budget": "",
          "Campaign_Objective": "",
          "Total_Ad_Spend": "",
          "Budget_Utilization_Percentage": ""
        }
      ],
      "Objective_Awareness": {
        "Metrics_Table": [
          {
            "Channel": "",
            "Total_Ad_Spend": "",
            "Impressions": "",
            "Unique_Reach": "",
            "Frequency": "",
            "ROAS": "",
            "CPM": ""
          }
        ]
      },
      "Objective_Consideration": {
        "Metrics_Table": [
          {
            "Channel": "",
            "Total_Ad_Spend": "",
            "Impressions": "",
            "Unique_Reach": "",
            "Clicks": "",
            "CTR": "",
            "CPC": "",
            "CPCV": "",
            "Viewed_Units": "",
            "Clicked_Units": "",
            "Add_To_Cart": ""
          }
        ]
      },
      "Objective_Conversion": {
        "Metrics_Table": [
          {
            "Channel": "",
            "Total_Ad_Spend": "",
            "Impressions": "",
            "Clicks": "",
            "CTR": "",
            "CVR": "",
            "Viewed_Transactions": "",
            "Clicked_Transactions": "",
            "Viewed_Revenue": "",
            "Clicked_Revenue": "",
            "Total_Campaign_Revenue": "",
            "ROAS": "",
            "Incremental_Sales_Lift": "",
            "Conversions": ""
          }
        ]
      },
      "Objective_Retention": {
        "Metrics_Table": [
          {
            "Channel": "",
            "Total_Ad_Spend": "",
            "Conversions": "",
            "CVR": "",
            "Transactions_Repeat": "",
            "Units_Sold": "",
            "Total_Campaign_Revenue": "",
            "Incremental_Sales_Lift": "",
            "ROAS": ""
          }
        ]
      }
    },
    "5.Campaign_Wise_Analysis": {
      "Visual_Layers_Per_Objective": [
        "Awareness",
        "Consideration",
        "Conversion",
        "Retention"
      ],
      "Visualizations": {
        "Impressions_Reach_Trend": "Line Chart",
        "CTR_Trend": "Line Chart",
        "Spend_vs_Revenue": "Column Chart",
        "ROAS_Trend": "Line Chart",
        "Frequency_Distribution": "Dual Axis Chart",
        "Add_to_Cart_Funnel": "Funnel Chart",
        "ROAS_by_Channel": "Bar Chart",
        "Channel_Comparison_Retention_CVR": "Bar Chart",
        "Viewed_vs_Clicked_Units": "Dual Axis Line",
        "Conversion_Funnel": "Funnel Chart",
        "Channel_wise_Reach_CPM": "Clustered Bar Chart",
        "CPA_vs_CVR": "Scatter Plot"
      },
      "Campaign_Details": [
        {
          "Campaign_Name": "",
          "Campaign_ID": "",
          "Campaign_Ad_IDs": [],
          "Campaign_Duration": "",
          "KPIs_Analyzed": [],
          "Campaign_Objective": "",
          "Metrics": {
            "Impressions": "",
            "ROAS": "",
            "Conversions": "",
            "CTR": ""
          },
          "Campaign_Analysis_Text": "",
          "Weekly_Performance": [
            {
              "Week": 1,
              "Conversions": "",
              "Revenue": ""
            },
            {
              "Week": 2,
              "Conversions": "",
              "Revenue": ""
            },
            {
              "Week": 3,
              "Conversions": "",
              "Revenue": ""
            },
            {
              "Week": 4,
              "Conversions": "",
              "Revenue": ""
            }
          ],
          "Overall_Campaign_Impact": ""
        }
      ],
      "Campaign_Comparison": {
        "Applicable_Condition": "Only if objective and SKUs are same",
        "Comparison_Notes": ""
      }
    },
    "6.Recommendations": [
      {
        "Title": "Granular Temporal and Contextual Analysis",
        "Action": "",
        "Objective": ""
      },
      {
        "Title": "Dynamic Budget Allocation and Bidding Strategy Optimization",
        "Action": "",
        "Objective": ""
      },
      {
        "Title": "Systematic A/B Testing of Creative and Landing Page Elements",
        "Action": "",
        "Objective": ""
      }
    ]
  }
}

"""
report_context= """This report is prepared for the Marketing and Sales leadership team to provide a comprehensive overview of campaign performance across different channels. The primary objective is to understand which channels contribute most effectively to attributed sales and to identify overall daily sales patterns. The insights derived from this analysis will be crucial in informing strategic decisions related to optimizing future marketing spend, resource allocation, and campaign targeting to maximize ROI.
"""
filters = {
    "persona": "Marketing Manager",
    "brand": "Dove",
    "platform": "Google Ads",
    "duration": "Last Quarter",
    "report_type": "Campaign Performance Report"
}
#######################################

def llm_call(prompt):
    model = GenerativeModel(os.getenv("TEXT_VIZ_JSON_AGENT"))
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.5,
            "top_p": 1.0,
            "max_output_tokens": 7168
        }
    )
    # print(f"llm response")
    # print(response)
    try:
        output_text = response.text.strip() if hasattr(response, "text") else ""
        if not output_text:
            return " No summary generated. Check LLM output or token limit."
        return output_text
    except Exception as e:
        return f" Error processing summary: {e}"

async def generate_report(tool_context: Optional[ToolContext] = None):
    """ 
    Generates report in Markdown format.
    """
    print("inside report summarization agent")
    print("inside generate report tool")

    summary = tool_context.state['text_viz_json']
    # template = report_template  
    template = tool_context.state['report_template']
    # context = report_context    
    context = tool_context.state['report_context']
    # filters = filters           
    filter = tool_context.state["filters"]
    filter_text = f"""**Filters:**
        Persona: {filters.get('persona', 'N/A')}
        Brand: {filters.get('brand', 'N/A')}
        Platform: {filters.get('platform', 'N/A')}
        Period: {filters.get('duration', 'N/A')}
        Report Type: {filters.get('report_type', 'N/A')}
        """
    
    # filters = tool_context.state.get['report_filters']
    # debug prints
    print(f"text_viz_json output: {summary}")
    print(f"report template passed: {template}")
    print(f"report context passed: {context}")
    print(f"report filters passed: {filter_text}")

    # Generate report markdown using LLM
    main_prompt = generate_report_prompt()
    custom_prompt = f"""
    **Task**
    Generate report based on the below information.

    **Input Parameters:**
    1.  **Text and Visualization Summary:**

        {summary}

    2.  **Report Template:**

        {template}

    3.  **Report Context:**

        {context}

    4.  **Filters:**

        {filter_text}

    **Output:**
    """
    prompt = main_prompt + custom_prompt
    res = llm_call(prompt)
    tool_context.state['report_markdown'] = res
    print("report markdown generated:")
    print(res)
    return "report markdown generated"
  

async def format_report(tool_context: Optional[ToolContext] = None):
    """
    Convert Report from markdown format to JSON format
    """
    print("inside format report tool")
    report = tool_context.state['report_markdown']
    main_prompt = format_report_prompt()
    custom_prompt = f"""
    **Task**
    Generate JSON from the Report given below. Do not violate safety filters while generating output. Remove just the things that violate safety rules and kept  of all the information in the Report.

    **Report:**

    {report}

    **Output:**
    """
    prompt = main_prompt + custom_prompt
    res = llm_call(prompt)
    tool_context.state['report_json'] = res
    print("report json generated: ")
    print(res)
    filename = "report_json.json"
        # Save to file in repo root (current working directory)
    root = os.getcwd()
    path = os.path.join(root, filename)

    # If `res` is not a JSON string, try to convert/pretty-print
    report_text = res
    try:
        if isinstance(res, (dict, list)):
            report_text = json.dumps(res, ensure_ascii=False, indent=2)
        else:
            # try to load and pretty print if it's a JSON string
            try:
                parsed = json.loads(res)
                report_text = json.dumps(parsed, ensure_ascii=False, indent=2)
            except Exception:
                # leave as-is (string)
                report_text = str(res)
    except Exception:
        report_text = str(res)

    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"Report JSON saved to: {path}")
    return "report formatted to json"