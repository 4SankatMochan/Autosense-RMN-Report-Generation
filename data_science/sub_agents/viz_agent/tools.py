import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import math
# import plotly.express as px

import io
import base64
from datetime import datetime
from typing import List, Optional
from google.genai.types import Part, Blob
from google.adk.tools import ToolContext

async def chart_plotting_tool(
    chart_type: str,
    title: str,
    categories: List[str] = [],
    values: List[float] = [],
    # values2: List[float] = [],
    
    x: List[float] = [],
    y: List[float] = [],
    # dates: List[str] = [],
    stages: List[str] = [],
    subcategories: List[str] = [],
    tool_context: Optional[ToolContext] = None
) -> dict:

    tool_context.state["chart_type"] = chart_type
    tool_context.state["x"] = x
    tool_context.state['y'] = y
    tool_context.state['categories'] = categories
    tool_context.state['values'] = values
    # tool_context.state['values[0]'] = values[0]
    # tool_context.state['values[1]'] = values[1]
    tool_context.state['title'] = title
    tool_context.state['stages'] = stages
    tool_context.state['subcategories'] = subcategories

    # print('chart_type', chart_type, flush = True)
    # print('x', x, flush = True)
    # print('y', y, flush = True)
    # print('categories', categories, flush = True)
    # print('values', values, flush = True)
    # print('title', title, flush = True)
    # print('stages', stages, flush = True)
    # print('subcategories', subcategories, flush = True)
    with open("debug_log.txt", "a") as f:
        f.write(f"chart_type: {chart_type}\n")
        f.write(f"x: {x}\n")
        f.write(f"y: {y}\n")
        f.write(f"categories: {categories}\n")
        f.write(f"values: {values}\n")
        f.write(f"title: {title}\n")    
        f.write(f"stages: {stages}\n")
        f.write(f"subcategories: {subcategories}\n")
        f.write("===="*100)
   
    if chart_type == "bar":
        base_width=7 
        base_points=30
        height = 4
        scale_factor = len(x) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))
        plt.bar(categories, values, color='skyblue')
        plt.xticks(rotation=90, fontsize=9)
        plt.yticks(fontsize=10)
        plt.xlabel("Category")
        plt.ylabel("Value")
    elif chart_type in ['line', 'trend line']:
        base_width=7 
        base_points=30
        height = 4

        scale_factor = len(x) / base_points
        width = max(base_width, base_width * scale_factor)

        plt.figure(figsize=(width, height))
        plt.plot(x,y)
        plt.xticks(rotation=45, fontsize=10)
        plt.yticks(fontsize=10)
        plt.xlabel('x_line')
        plt.ylabel('y_line')

    elif chart_type == "pie":
        plt.pie(values, labels=categories, autopct='%1.1f%%', startangle=140)

    elif chart_type == "waterfall":
        cum_values = np.cumsum([0] + values[:-1])
        colors = ['green' if v >= 0 else 'red' for v in values]
        for i in range(len(values)):
            plt.bar(categories[i], values[i], bottom=cum_values[i], color=colors[i])
        plt.xlabel("Step")
        plt.ylabel("Value")

    elif chart_type == "scatter":
        plt.scatter(x, y, color='purple')
        plt.xlabel("X")
        plt.ylabel("Y")

    elif chart_type == "area":
        # print(f"calling from Are matplotlib tool")
        # plt.fill_between(x, y, color='lightgreen', alpha=0.7)
        plt.fill_between(categories, values, color='lightgreen', alpha=0.7)
        # plt.plot(x, y, color='green')
        plt.plot(categories, values, color='green')
        plt.xlabel("X")
        plt.ylabel("Y")

    elif chart_type == "funnel":
        for i in range(len(stages)):
            plt.barh(stages[i], values[i], color='steelblue', height=0.6)
        plt.xlabel("Value")

    elif chart_type == "donut":
        wedges, texts, autotexts = plt.pie(values, labels=categories, autopct='%1.1f%%', startangle=140)
        centre_circle = plt.Circle((0, 0), 0.70, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
    elif chart_type in ["box", "box plot", 'box_plot']:
    #     df = pd.DataFrame({'category': categories, 'value': values})
    #     # Group values by category
    #     grouped_data = [group['value'].values for name, group in df.groupby('category')]
    #     # Get unique categories to use as labels (sorted for consistency)
    #     labels = sorted(df['category'].unique())
    #     plt.boxplot(grouped_data, labels=labels)
    #     plt.ylabel("Value")
    #     plt.title("Box Plot by Category")
    #     plt.show()
        plt.boxplot(values, patch_artist=True, notch=True, vert=True)
        # plt.plot()
    elif chart_type == "bubble":
        df = pd.DataFrame({'x': x, 'y':y})
        # Normalize y between 0.1 and 1
        min_norm = 0.1
        max_norm = 1.0
        y_min = df['y'].min()
        y_max = df['y'].max()
        normalized = (df['y'] - y_min) / (y_max - y_min)
        df['size'] = normalized
        df['size'] = df['size']*200
        plt.scatter(df['x'], df['y'], s = df['size'], alpha=0.5)
        plt.xticks(df['x'])
        plt.xlabel("X_bubble")
        plt.ylabel("Y_bubble")

    # elif chart_type in ["dual_axis",'dual axis']:
    #     df = pd.DataFrame({'category': categories, 'value1': values, 'value2': values2})
    #     fig, ax1 = plt.subplots()
    #     # Plot on the first y-axis
    #     color1 = 'tab:blue'
    #     ax1.set_xlabel("Category")
    #     ax1.set_ylabel("Value 1", color=color1)
    #     ax1.plot(df['category'], df['value1'], color=color1)
    #     ax1.tick_params(axis='y', labelcolor=color1)

    #     # Create second y-axis
    #     ax2 = ax1.twinx()
    #     color2 = 'tab:red'
    #     ax2.set_ylabel("Value 2", color=color2)
    #     # Plot on the second y-axis
    #     ax2.plot(df['category'], df['value2'], color=color2)
    #     ax2.tick_params(axis='y', labelcolor=color2)
    elif chart_type == 'heatmap':
        df = pd.DataFrame({'category': categories, 'value': values})
        labels = df['category'].to_list()
        values = df['value'].to_list()
        N = len(values)
        # Determine grid size (cols and rows)
        cols = math.ceil(math.sqrt(N))  # Try for a square-ish shape
        rows = math.ceil(N / cols)

        # Pad the values and labels to fill the grid completely
        pad_size = rows * cols - N
        labels += [''] * pad_size
        values += [np.nan] * pad_size

        labels_array = np.array(labels).reshape(rows, cols)
        values_array = np.array(values).reshape(rows, cols)

        # Plot
        fig, ax = plt.subplots(figsize=(cols * 2, rows * 1.5))
        heatmap = ax.imshow(values_array, cmap= 'YlOrRd')

        # Add text labels (label + value)
        for i in range(rows):
            for j in range(cols):
                if labels_array[i, j] != '':
                    value_text = f'{values_array[i, j]:.0f}' if not np.isnan(values_array[i, j]) else ''
                    ax.text(j, i, f'{labels_array[i, j]}\n{value_text}',
                            ha='center', va='center', color='black', fontsize=9)

        # Remove axis ticks
        ax.set_xticks([])
        plt.colorbar(heatmap)
    elif chart_type == "radial gauge":
        sales_val = values[0]
        target_val = values[1]

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
        fig.text(0.5, 0.3, f'Sales: ${sales_val:,.0f} | Target: ${target_val:,.0f}', fontsize=12, ha='center', va='center')
        
    
    elif chart_type == "pareto":

        df = pd.DataFrame({'category': categories, 'value': values})
        df_sorted = df.sort_values(by='value', ascending=False).reset_index(drop=True)

        # Calculate cumulative percentage
        df_sorted['cumulative_percentage'] = (df_sorted['value'].cumsum() /
                                              df_sorted['value'].sum()) * 100

        ax1 = plt.gca()

        # Bar plot for frequencies
        ax1.bar(df_sorted['category'], df_sorted['value'], color='skyblue')
        ax1.set_xlabel("Category Pareto")
        ax1.set_ylabel("Frequency Pareto", color='skyblue')
        ax1.tick_params(axis='y', labelcolor='skyblue')
        plt.xticks(rotation=45, ha='right')

        # Line plot for cumulative percentage on a second y-axis
        ax2 = ax1.twinx()
        ax2.plot(df_sorted['category'],
                 df_sorted['cumulative_percentage'],
                 color='red', marker='o', ms=5)
        ax2.set_ylabel("Cumulative Percentage (%)", color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        ax2.set_ylim(0, 105)
    elif chart_type == "stacked bar":
        catDf = pd.DataFrame(categories, columns = ['category']).drop_duplicates()
        subCatDf = pd.DataFrame(subcategories, columns = ['subcategory']).drop_duplicates()
        df = pd.merge(catDf, subCatDf, how = 'cross')
        df['value'] = values
        # Pivot to make stacking easier
        pivot_df = df.pivot(index='category', columns='subcategory', values='value').fillna(0)

        # Bottom for stacking
        bottom = [0] * len(pivot_df)
        fig, ax = plt.subplots(figsize=(10, 6))
        # Plot each subcategory
        for subcategory in pivot_df.columns:
            ax.bar(pivot_df.index, pivot_df[subcategory], bottom=bottom, label=subcategory)
            # Update bottom
            bottom = bottom + pivot_df[subcategory]
        ax.legend(title='Subcategory', loc='upper right')
        plt.xticks(rotation=45)

    # elif chart_type== 'sunburst':
    #     df = pd.DataFrame({'category': categories,
    #                         'subcategory':subcategories,
    #                         'value': values})
    #     # Create sunburst plot
    #     fig = px.sunburst(
    #         df,
    #         path=['category', 'subcategory'],  # Hierarchical order
    #         values='value',
    #     )



    plt.title(title, fontsize=12)
    plt.tight_layout()


    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"chart_{timestamp}.png"
    plt.savefig(output_file)

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_bytes = buf.read()
    plt.close()

    # Create Part object
    image_artifact = Part(
        inline_data=Blob(data=image_bytes, mime_type="image/png")
    )

    # Correct async artifact registration
    await tool_context.save_artifact(output_file, image_artifact)

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
