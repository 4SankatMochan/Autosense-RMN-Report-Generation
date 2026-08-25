import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
import numpy as np
import math
import textwrap  # For automatic line wrapping
# import plotly.express as px

import io
import base64
import json
from datetime import datetime
from typing import List, Optional
from google.genai.types import Part, Blob
from google.adk.tools import ToolContext
from uuid import uuid4

async def chart_plotting_tool(
    chart_type: str,
    title: str,
    x :str,
    y : List[str],
    categorical_columns : List[str],
    continuous_columns : List[str],
    x_axis_label: str,
    y_axis_label: str,
    series_by: Optional[str] = "",
    tool_context: Optional[ToolContext] = None
) -> dict:

    tool_context.state["chart_type"] = chart_type
    tool_context.state["x_axis_label"] = x_axis_label
    tool_context.state["y_axis_label"] = y_axis_label
    tool_context.state["x"] = x
    tool_context.state['y'] = y
    tool_context.state['title'] = title
    tool_context.state['categorical_columns'] = categorical_columns
    tool_context.state['continuous_columns'] = continuous_columns
    tool_context.state['series_by'] = series_by
    print(f"Inside plot tool {chart_type}")

    def chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, chart_data):
        json_formate = {
                        "chart_type": chart_type,
                        "x_axis_label": x_axis_label,
                        "y_axis_label": y_axis_label,
                        "x": x,
                        "y": y,
                        "title": title,
                        "series_by": series_by,
                        "data": json.loads(chart_data.to_json(orient='records')),
                            }
        return json_formate

    db_data = tool_context.state.get("query_result")
    db_data = pd.DataFrame(db_data)

    print(f"[viz_agent] chart_type={chart_type} x={x} y={y} title={title[:60]!r} session={tool_context._invocation_context.session.id}")


    def get_suffix_scale(max_val):
        if max_val >= 1e12:
            return 1e12, 'T'
        elif max_val >= 1e9:
            return 1e9, 'B'
        elif max_val >= 1e6:
            return 1e6, 'M'
        elif max_val >= 1e3:
            return 1e3, 'K'
        else:
            return 1, ''
    # Helper function to format values
    def legend_formate(num):
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        else:
            return str(num)
    def format_with_suffix(value):
        scale_val, suffix_val = get_suffix_scale(value)
        return f'{value / scale_val:.0f}{suffix_val}'
    # Formatter function using the detected scale
    def dynamic_format(num, pos):
        return f'{num / scale:.1f}' if num != 0 else '0'
    if chart_type == "bar":
        if len(y)==1:
            max_val = np.max(db_data[y])
            scale, suffix = get_suffix_scale(max_val)

            base_width=7
            base_points=30
            height = 4

            scale_factor = len(db_data) / base_points
            width = max(base_width, base_width * scale_factor)

            plt.figure(figsize=(width, height))

            # Plot
            plt.figure(figsize=(width, height))
            print(width, height)
            ax = db_data.plot(kind='bar', x= x, y=y, width=0.7)

            # Apply formatter
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
            # Labels and title
            plt.title(title)
            plt.ylabel(f'{y_axis_label} ({suffix})')
            plt.xlabel(f'{x_axis_label}')
            plt.xticks(rotation=90)
            plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='Categories')


            # Annotate values on bars
            for p in ax.patches:
                height = p.get_height()
                ax.annotate(f'{format_with_suffix(height)}',
                            (p.get_x() + p.get_width() / 2, height),
                            ha='center', va='bottom', fontsize=8)

        else:
            # --- Identify Columns ---
            category_col = [x]               # e.g. 'channel'
            value_cols = y                 # e.g. ['total_campaign_budget', 'total_planned_spend']

            # --- Determine Scale (K, M, B) ---
            max_val = db_data[value_cols].values.max()
            scale, suffix = get_suffix_scale(max_val)
            # --- Plotting ---
            bar_width = 0.8 / len(value_cols)  # Total width per group is 0.8
            x_loc = np.arange(len(db_data[category_col]))  # X locations

            base_width=7
            base_points=30
            height = 4

            scale_factor = len(db_data)*len(value_cols) / base_points
            width = max(base_width, base_width * scale_factor)

            plt.figure(figsize=(width, height))

            # Plot each numeric column
            for i, col in enumerate(value_cols):
                offset = (i - (len(value_cols)-1)/2) * bar_width
                plt.bar(x_loc + offset, db_data[col], width=bar_width, label=col)

                # Annotate each bar
                for xi, val in zip(x_loc, db_data[col]):
                    plt.text(xi + offset, val, format_with_suffix(val),
                            ha='center', va='bottom', fontsize=8)
            plt.xticks(x_loc, db_data[category_col].squeeze().tolist(), rotation=90)
        # --- Formatting ---
        
        plt.ylabel(f'{y_axis_label} ({suffix})')
        plt.xlabel(f'{x_axis_label}')
        plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='Categories')
        plt.gca().yaxis.set_major_formatter(FuncFormatter(dynamic_format))
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
        # plt.xticks(rotation=90, fontsize=9)
        # plt.yticks(fontsize=10)
        # plt.xlabel(x_axis_label)
        # plt.ylabel(f"{y_axis_label} ({suffix})")
    elif chart_type in ['line', 'trend line']:
        if series_by =="":
            base_width=7 
            base_points=30
            height = 4

            scale_factor = len(db_data) / base_points
            width = max(base_width, base_width * scale_factor)

            max_val = np.max(db_data[y].values)
            scale, suffix = get_suffix_scale(max_val)

            plt.figure(figsize=(width, height))
            db_data.sort_values(x, inplace = True)
            plt.plot(db_data[x], db_data[y])
            for i, col in enumerate(y):
                plt.plot(db_data[x], db_data[col], label=col)
                
                # Annotate points
                for x_val, y_val in zip(db_data[x], db_data[col]):
                    plt.annotate(f'{format_with_suffix(y_val)}',
                                (x_val, y_val),
                                textcoords="offset points",
                                xytext=(0, 5),
                                ha='center',
                                fontsize=8
                                )

            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
            plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='categories')
        else:
            
            base_width=7 
            base_points=30
            height = 4

            scale_factor = len(db_data) / base_points
            width = max(base_width, base_width * scale_factor)

            max_val = np.max(db_data[y].values)
            scale, suffix = get_suffix_scale(max_val)
            plt.figure(figsize=(width, height))
            db_data.sort_values(x, inplace = True)
            pivot_df = db_data.pivot_table(
                index=x,
                columns=series_by,
                values=y,
                aggfunc='mean'
            ).fillna(0)

            # Reset index so 'daily_date' becomes a column again
            pivot_df = pivot_df.reset_index()

            # Start a new figure


            # Plot each channel manually using string x-axis
            for col in pivot_df.columns[1:]:  # skip the first column (x)
                plt.plot(pivot_df[x], pivot_df[col], marker='o', label=col)

                # Annotate each point
                for i, val in enumerate(pivot_df[col]):
                    plt.annotate(
                        f'{format_with_suffix(val)}',
                        (pivot_df[x][i], val),
                        textcoords="offset points",
                        xytext=(0, 8),
                        ha='center',
                        fontsize=9
                    )

            # Add titles and labels

            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
            plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title= series_by)
        plt.xticks(rotation=90, fontsize=10)
        plt.xlabel(f'{x_axis_label}')
        plt.ylabel(f'{y_axis_label}{(suffix)}',fontsize=10)
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif chart_type == "pie":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data[y]) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))
        wedges, texts, autotexts = plt.pie(
            db_data[y].squeeze().tolist(),
            labels=db_data[x].squeeze().tolist(),
            autopct='%1.1f%%',
            startangle=90,
            textprops={'color': 'white'}
                                    )

        # Create custom legend labels with values
        legend_labels = [f"{cat}: {legend_formate(val)}" for cat, val in zip(db_data[x].squeeze().tolist(),  db_data[y].squeeze().tolist())]

        # Add legend
        plt.legend(wedges, legend_labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0.5))

        # Ensure circle aspect ratio
        plt.axis('equal')
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)

    elif chart_type == "waterfall":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))

        max_val = np.max(db_data[y])
        scale, suffix = get_suffix_scale(max_val)
        categories = db_data[x].squeeze().tolist()
        values = db_data[y].squeeze().tolist()
        cum_values = np.cumsum([0] + values[:-1])
        colors = ['green' if v >= 0 else 'red' for v in values]
        for i in range(len(values)):
            plt.bar(categories[i], values[i], bottom=cum_values[i], color=colors[i])
            # Add text label to each bar
            y_pos = cum_values[i] + values[i] / 2  # Center of the bar
            label = f'{format_with_suffix(values[i])}'
            plt.text(categories[i], y_pos, label, ha='center', va='center', fontsize=8, color='white')

        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        plt.xlabel(x_axis_label)
        plt.xticks(rotation=90, fontsize=9)
        plt.ylabel(f"{y_axis_label} ({suffix})")
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif chart_type == "scatter":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(db_data[y])
        scale, suffix = get_suffix_scale(max_val)
        plt.figure(figsize=(width, height))
        plt.scatter(db_data[x], db_data[y], color='purple')
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        plt.xlabel(x_axis_label)
        plt.xticks(rotation=90, fontsize=9)
        plt.ylabel(f"{y_axis_label} ({suffix})")
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif chart_type == "area":
        base_width = 7
        base_points = 30
        height = 4
        values = db_data[y].squeeze().tolist()
        categories = db_data[x].squeeze().tolist()
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)

        plt.figure(figsize=(width, height))
        categories = db_data[x].squeeze().tolist()
        values = db_data[y].squeeze().tolist()
        plt.fill_between(categories, values, color='lightgreen', alpha=0.7)
        # plt.plot(x, y, color='green')
        plt.plot(categories, values, color='green')
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        for i, val in enumerate(values):
            label = f'{format_with_suffix(val)}'
            plt.annotate(
                label,
                xy=(categories[i], val),          # Point to annotate
                xytext=(1, 6),                    # Offset: 5 points above
                textcoords='offset points',      # Interpret offset in display points
                ha='center',
                va='bottom',
                fontsize=8
                        )
        plt.xlabel(x_axis_label)
        plt.xticks(rotation=90, fontsize=9)
        plt.ylabel(f"{y_axis_label} ({suffix})")
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif chart_type == "funnel":
        base_width = 7
        base_points = 30
        height = 4
        categories = db_data[x].squeeze().tolist()
        values = db_data[y].squeeze().tolist()
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)
        plt.figure(figsize=(width, height))



        for i in range(len(categories)):
            plt.barh(categories[i], values[i], color='steelblue', height=0.6)

            # Create and place the label
            label = f'{format_with_suffix(values[i])}'
            plt.text(
                values[i],               # x position (end of the bar)
                categories[i],               # y position (same as bar)
                label,
                va='center',             # vertically center the text
                ha='left',               # place it just to the right of the bar
                fontsize=8,
                color='black'
            )
        formatter = FuncFormatter(dynamic_format)
        plt.gca().xaxis.set_major_formatter(formatter)
        plt.xlabel(f"{y_axis_label} ({suffix})")
        plt.xticks(rotation=90, fontsize=9)
        plt.ylabel(x_axis_label)
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif chart_type == "donut":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))

        wedges, texts, autotexts = plt.pie(db_data[y].squeeze().tolist(),
            labels=db_data[x].squeeze().tolist(),
            autopct='%1.1f%%',
            startangle=90,
            textprops={'color': 'black'}
                                    )
        centre_circle = plt.Circle((0, 0), 0.70, fc='white')
        # Create custom legend labels with values
        legend_labels = [f"{cat}: {legend_formate(val)}" for cat, val in zip(db_data[x].squeeze().tolist(),  db_data[y].squeeze().tolist())]

        # Add legend
        plt.legend(wedges, legend_labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0.5))
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)   
        
    elif chart_type in ["box", "box plot", 'box_plot']:
        try:
            # Group data by channel
            grouped = db_data.groupby(x)[y[0]].apply(list)

            # Plotting
            base_width = 10
            base_points = 30
            height = 4
            scale_factor = len(db_data) / base_points
            values = db_data[y].squeeze().tolist()
            width = max(base_width, base_width * scale_factor)
            max_val = np.max(values)
            scale, suffix = get_suffix_scale(max_val)
            plt.figure(figsize=(width, height))
            plt.boxplot(grouped.tolist(), labels=grouped.index.tolist())
            plt.boxplot(values, patch_artist=True, notch=True, vert=True)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
        except:
            base_width = 7
            base_points = 30
            height = 4
            scale_factor = len(db_data) / base_points
            values = db_data[y].squeeze().tolist()
            width = max(base_width, base_width * scale_factor)
            max_val = np.max(values)
            scale, suffix = get_suffix_scale(max_val)
            plt.figure(figsize=(width, height))
            plt.boxplot(values, patch_artist=True, notch=True, vert=True)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)


        plt.xlabel(f'{x_axis_label}')
        plt.ylabel(f'{y_axis_label}({suffix})')
        plt.xticks(rotation=90)
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    
        

    elif chart_type == "bubble":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(db_data[y[1]].values)
        scale, suffix = get_suffix_scale(max_val)
        plt.figure(figsize=(width, height))
        plt.scatter(db_data[x], db_data[y[0]], s = db_data[y[1]], alpha=0.5)
        plt.xticks(db_data[x])
        for i, row in db_data.iterrows():
            plt.text(row[x], row[y[0]], f"{format_with_suffix(row[y[1]])}", fontsize=9, ha='center', va='center')
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        plt.xlabel(x_axis_label)
        plt.xticks(rotation=90, fontsize=9)
        plt.ylabel(f"{y_axis_label} ({suffix})")
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)

    elif chart_type == 'heatmap':
    # Prepare DataFrame and extract labels/values
        categories = db_data[x].squeeze().tolist()
        values = db_data[y].squeeze().tolist()
        # df = pd.DataFrame({'category': categories, 'value': values})
        labels = categories
        values = values
        N = len(values)

        # Determine grid size
        cols = math.ceil(math.sqrt(N))
        rows = math.ceil(N / cols)

        # Pad lists to fill grid
        pad_size = rows * cols - N
        labels += [''] * pad_size
        values += [np.nan] * pad_size

        # Reshape into 2D arrays
        labels_array = np.array(labels).reshape(rows, cols)
        values_array = np.array(values).reshape(rows, cols)

        # Plot
        plt.figure(figsize=(cols * 2, rows * 1.5))
        plt.imshow(values_array, cmap='YlOrRd')

        # Annotate cells
        ax = plt.gca()
        for i in range(rows):
            for j in range(cols):
                label = labels_array[i, j]
                val = values_array[i, j]
                if label != '':
                    # value_text = f'{val:.0f}' if not np.isnan(val) else ''
                    value_text = f'{format_with_suffix(val)}'
                    ax.text(j, i, f'{label}\n{value_text}',
                            ha='center', va='center', color='black', fontsize=9)
        # Clean up axes
        ax.set_xticks([])
        ax.set_yticks([])

        # Add colorbar
        plt.colorbar()
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif chart_type == "radial gauge":
        sales_val = db_data.iloc[0,0]
        target_val = y[1]

        if target_val > 0:
            value = (sales_val / target_val) * 100
        else:
            value = 0

        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})

        # Define gauge range
        min_val = 0
        max_val = 120  # Max value on the gauge, e.g., 120% to show overachievement

        # Polar settings
        ax.set_theta_offset(np.pi)  # Start at 180 degrees (left)
        ax.set_theta_direction(-1)  # Clockwise
        # ax.set_rlim(0, 1)
        ax.set_axis_off()           # Hide grid, axes, etc.

        # Color zones
        zones = [
            (0, 50, 'lightcoral'),
            (50, 90, 'gold'),
            (90, 100, 'lightgreen'),
            (100, max_val, 'deepskyblue')  # Overachievement
        ]
        for start, end, color in zones:
            start_angle = np.pi * (start - min_val) / (max_val - min_val)
            end_angle = np.pi * (end - min_val) / (max_val - min_val)
            theta = np.linspace(start_angle, end_angle, 100)
            r = np.ones_like(theta) * 0.9
            ax.plot(theta, r, lw=20, color=color)

        # Needle
        capped_value = min(value, max_val)
        value_angle = np.pi * (capped_value - min_val) / (max_val - min_val)
        ax.plot([value_angle, value_angle], [0, 0.95], color='black', lw=2)
        ax.plot(0, 0, 'o', markersize=10, color='black')  # center circle
        fig.text(0.5, 0.4, f'{value:.1f}%', fontsize=24, fontweight='bold', ha='center', va='center')
        fig.text(0.5, 0.3, f'Value: ${sales_val:,.0f} | Target: ${target_val:,.0f}', fontsize=12, ha='center', va='center')
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)       
    
    elif chart_type == "pareto":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(db_data[y])
        scale, suffix = get_suffix_scale(max_val)

        df = pd.DataFrame({'category': db_data[x].squeeze().tolist(), 'value': db_data[y].squeeze().tolist()})
        df_sorted = df.sort_values(by='value', ascending=False).reset_index(drop=True)

        # Calculate cumulative percentage
        df_sorted['cumulative_percentage'] = (df_sorted['value'].cumsum() /
                                            df_sorted['value'].sum()) * 100
        plt.figure(figsize=(width, height))
        ax1 = plt.gca()

        # Bar plot for frequencies
        bars = ax1.bar(df_sorted['category'], df_sorted['value'], color='skyblue')
        ax1.set_xlabel(x_axis_label)
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        ax1.set_ylabel(f"{y_axis_label} ({suffix})", color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
        plt.xticks(rotation=90, ha='right')
        # Annotate bar values
        for bar, val in zip(bars, df_sorted['value']):
            ax1.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{format_with_suffix(val)}",
                    ha='center', va='bottom', fontsize=9, color='black')

        # Line plot for cumulative percentage on a second y-axis
        ax2 = ax1.twinx()
        ax2.plot(df_sorted['category'],
                df_sorted['cumulative_percentage'],
                color='red', marker='o', ms=5)
        for x, y in zip(df_sorted['category'], df_sorted['cumulative_percentage']):
            ax2.text(x, y + 2, f"{y:.1f}%", ha='center', va='bottom', fontsize=9, color='red')
        ax2.set_ylabel("Cumulative Percentage (%)", color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        ax2.set_ylim(0, 105)
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)
    elif 'stacked' in chart_type.lower():
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(db_data) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(db_data[y].values)
        scale, suffix = get_suffix_scale(max_val)
        if series_by !="":
            # Aggregate daily_reach by date and channel (pivot)
            df_pivot = db_data.pivot_table(index= x, columns= series_by, values= y, aggfunc='sum').fillna(0)

            # Plot stacked bar chart
            ax = df_pivot.plot(kind='bar', stacked=True, figsize=(width, height))
        else:
            # Set campaign_id as index
            db_data.set_index(x, inplace=True)

            # Generalized: select only numeric columns to plot (in case extra text columns are added)
            df_numeric = db_data[y]

            # Create figure
            plt.figure(figsize=(width, height))

            # Track bottom for stacking
            bottom = [0] * len(df_numeric)

            # Plot each column in stack
            for col in df_numeric.columns:
                plt.bar(df_numeric.index, df_numeric[col], bottom=bottom, label=col)
                bottom = [i + j for i, j in zip(bottom, df_numeric[col])]

        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)

        plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='Categories')
        plt.xticks(rotation=90)
        plt.xlabel(x_axis_label)
        plt.ylabel(f"{y_axis_label} ({suffix})")
        json_data = chart_meta_data(chart_type, x,y, x_axis_label, y_axis_label,title, series_by, db_data)

    tool_context.state['chart_metaData_json'] = json_data
    json_string = json.dumps(json_data)
    wrapped_title = "\n".join(textwrap.wrap(title, width=40))  # Wrap every ~40 characters
    plt.title(wrapped_title, fontsize=12)
    plt.tight_layout()


    output_file = f"VizChart.png"
    # Save to in-memory buffer only — no local disk write
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
        

    buf.seek(0)
    image_bytes = buf.read()
    plt.close()

    # Create Part object
    image_artifact = Part(
        inline_data=Blob(data=image_bytes, mime_type="image/png")
    )
    # Json artifacts
    json_artifact = Part(
        inline_data=Blob(
            # mime_type="application/json", # multi agent has issue while sending json as artifact in GCS. text is recommended method.
            mime_type = 'text/plain',
            data=json_string.encode('utf-8')
        )
    )
    artifact_name = tool_context.state.get('artifact_name')
    folder_name = str(artifact_name).lower()
    image_path = f"{folder_name}_{output_file}"
    json_path = f"{folder_name}_data.json"
    # # Correct async artifact registration
    # await tool_context.save_artifact(output_file, image_artifact)
    # await tool_context.save_artifact('data.json', json_artifact)
    await tool_context.save_artifact(image_path, image_artifact)
    await tool_context.save_artifact(json_path, json_artifact)

    # Return both artifact reference and base64 image
    return {
        "artifact": {
            "name": output_file,
            "type": "image/png",
            "description": title
        },
        "image": {
            "src": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}",
            "alt": title
        }
    }
