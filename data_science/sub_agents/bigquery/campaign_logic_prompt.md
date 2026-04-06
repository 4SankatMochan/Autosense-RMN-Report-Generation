# Campaign Logic Prompt

## Purpose
- This prompt defines the **business rules, logic, and enrichment calculations** for working with the `RMN_Campaign_Dataset_Dev` database.  
- It ensures that campaign analysis queries and simulated metrics are **consistent, schema-aligned, and business-valid**.  
- **Source hierarchy** for reference:  
  - Field names and data types → from **live BigQuery schema** (preferred)  
  - Enum values, relationships, and business semantics → from **data_dictionary.json**  
  - Business rules and metric calculations → from **campaign_logic_prompt.md**  
- Use `data_dictionary.json` as fallback if the live BigQuery schema is not accessible.  

---

## Business Rules & Standard Metrics
- **ROAS (Return on Ad Spend)** = `attributed_sales_value / actual_spend_to_date`  
- **CTR (Click-Through Rate)** = `ctr_percent`  
- **Conversion Rate** = `conversion_rate_percent`  
- **CPC (Cost Per Click)** = `actual_spend_to_date / clicks`  
- Apply **date filters** for time-based queries  

## Aggregation Rules
- Important data processing rules when aggregating (**When daily basis values not required rather a single value for overall duration required.**):  
                **Aggregation Rules**
                Dataset contains daily record of Campaigns for any brand. So, If aggregate( Sum, Max , Min etc) values required follow these rules:
            
                **GROUPING**
                Group by Channels only unless user specifies otherwise.
                Donot at all groupby date in aggredation cases, as dates are only unique identity and there's no point in grouping by date.
            
                METRIC AGGREGATION Rules (must follow)
            
                ## Additive Metrics → SUM
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
            
                ##Reach Metrics
                Unique_Reach → MAX or DISTINCT per channel
            
                Actual_spend_to_date → MAX
                **Planned Spend → Any (Do not sum at all)
            
                Derived Metrics
                Compute AFTER aggregation.
         
                **Important in the above case**
            
                -Never aggregate or average pre-calculated KPI columns.
                -Always recompute them from base metrics after aggregation.
                -Group on channel basis unless otherwise specified.
                
- Handle **NULLs** carefully  

---

## Metrics Calculation Logic
1. **Impressions** → Random integer 1,000–10,000  
2. **Frequency** → Random float (business-defined min/max per media & channel)  
3. **Reach** → `impressions / frequency` (floored)  
4. **CTR** → `clicks / impressions`, clamped to valid range  
5. **CPC & CPA** → Randomly sampled within ranges per media/channel  
6. **Clicks & Conversions** →  
   - `spend / CPC` (clicks)  
   - `spend / CPA` (conversions)  
   - Rounded to integers  
7. **Conversion Rate** → `conversions / clicks` (clamped to range)  
8. **ROAS & Attributed Sales** →  
   - ROAS within range  
   - Attributed Sales = `spend * ROAS`  
   - Clamp if out of bounds  
9. **Final CPC & CPA** →  
   - `spend / clicks` and `spend / conversions`  
   - Strictly clamped to valid ranges  

---

## Schema and Relationships
- The **complete schema** (tables, columns, data types, enums, and constraints) is maintained in `data_dictionary.json`.  
- Always reference the JSON file for **accurate schema details**.  
- Key entity relationships (see full details in `data_dictionary.json`):  
  - Campaign Metadata → Campaign Performance (1:many)  
  - Campaign Metadata → Clickstream (1:many via campaign_ad_id)  
  - Campaign Metadata → Transaction Data (1:many)  
  - Clickstream → Transaction Data (via user_id)  
  - Campaign Performance ↔ Audience Data (many:many)  

---

## Validation Checklist
Before finalizing any query or metric calculation, confirm:  
- Did I use field names and datatypes from the live BigQuery schema?  
- Did I reference enums, relationships, and business context from `data_dictionary.json`?  
- Did I apply ROAS/CTR/CPC/CVR rules from this prompt?  
- Did I clamp metrics to valid ranges (when enrichment logic applies)?  
- Did I include helpful comments in SQL?  
- Did I apply date filters when relevant?  

---

## Summary
- **Schema**: `data_dictionary.json` (field names, enums, relationships) + live BigQuery schema (preferred).  
- **Business rules**: this `campaign_logic_prompt.md`.  
- **Consistency**: All queries and enrichments must align with these rules to ensure results are internally valid and business-ready.  
