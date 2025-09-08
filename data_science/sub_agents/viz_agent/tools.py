import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
import numpy as np
import math
import textwrap  # For automatic line wrapping
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
    x_axis_label :str,
    y_axis_label :str,
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
    tool_context.state["x_axis_label"] = x_axis_label
    tool_context.state["y_axis_label"] = y_axis_label
    tool_context.state["x"] = x
    tool_context.state['y'] = y
    tool_context.state['categories'] = categories
    tool_context.state['values'] = values
    # tool_context.state['values[0]'] = values[0]
    # tool_context.state['values[1]'] = values[1]
    tool_context.state['title'] = title
    tool_context.state['stages'] = stages
    tool_context.state['subcategories'] = subcategories

    with open("debug_log.txt", "a") as f:
        f.write(f"chart_type: {chart_type}\n")
        f.write(f"x_axis_label: {x_axis_label}\n")
        f.write(f"y_axis_label: {y_axis_label}\n")
        f.write(f"x: {x}\n")
        f.write(f"y: {y}\n")
        f.write(f"categories: {categories}\n")
        f.write(f"values: {values}\n")
        f.write(f"title: {title}\n")    
        f.write(f"stages: {stages}\n")
        f.write(f"subcategories: {subcategories}\n")
        f.write("===="*100)

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
        # base_width=7 
        # base_points=30
        # height = 4
        # scale_factor = len(x) / base_points
        # width = max(base_width, base_width * scale_factor)
        # plt.figure(figsize=(width, height))
        # plt.bar(categories, values, color='skyblue')
        # plt.xticks(rotation=90, fontsize=9)
        # plt.yticks(fontsize=10)
        # plt.xlabel(x_axis_label)
        # plt.ylabel(y_axis_label)
        if subcategories:
            max_val = np.max(values)
            scale, suffix = get_suffix_scale(max_val)
            # Formatter function using the detected scale
            df = pd.DataFrame({
                                'categories': categories,
                                'subcategories': subcategories,
                                'values': values
                                    })

            base_width=7 
            base_points=30
            height = 4
            scale_factor = len(df) / base_points
            width = max(base_width, base_width * scale_factor)
            plt.figure(figsize=(width, height))

            # Pivot for grouped bar plot
            pivot_df = df.pivot(index='categories', columns='subcategories', values='values')
            pivot_df = pivot_df[list(df['subcategories'].unique())]  # Ensure correct order

            # Plot
            plt.figure(figsize=(width, height))
            ax = pivot_df.plot(kind='bar', width=0.7)

            # Annotate values on bars
            for p in ax.patches:
                height = p.get_height()
                ax.annotate(f'{format_with_suffix(height)}',
                            (p.get_x() + p.get_width() / 2, height),
                            ha='center', va='bottom', fontsize=8)
            # Apply formatter
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
            plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='Categories')
        else:
            max_val = np.max(values)
            scale, suffix = get_suffix_scale(max_val)

            # Formatter function using the detected scale
            df = pd.DataFrame({
                                'categories': categories,
                                'values': values
                            })

                # Plot
            base_width=7 
            base_points=30
            height = 4
            scale_factor = len(df) / base_points
            width = max(base_width, base_width * scale_factor)
            plt.figure(figsize=(width, height))

            ax = plt.bar(df['categories'], df['values'], color='skyblue')

            # Add value labels
            for i, v in enumerate(df['values']):
                plt.text(i, v, format_with_suffix(v), ha='center', va='bottom', fontsize=8)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)

        plt.xticks(rotation=90, fontsize=9)
        plt.yticks(fontsize=10)
        plt.xlabel(x_axis_label)
        plt.ylabel(f"{y_axis_label} ({suffix})")
    elif chart_type in ['line', 'trend line']:
        # base_width=7 
        # base_points=30
        # height = 4

        # scale_factor = len(x) / base_points
        # width = max(base_width, base_width * scale_factor)

        # plt.figure(figsize=(width, height))
        # plt.plot(x,y)
        # plt.xticks(rotation=90, fontsize=10)
        # plt.yticks(fontsize=10)
        # plt.xlabel(x_axis_label)
        # plt.ylabel(y_axis_label)
        if subcategories:
            max_val = np.max(y)
            scale, suffix = get_suffix_scale(max_val)
            # Create DataFrame
            df = pd.DataFrame({
                'x': x,
                'y': y,
                'subcategories': subcategories
            })

            # Figure size scaling
            base_width = 7
            base_points = 30
            height = 4
            scale_factor = len(df) / base_points
            width = max(base_width, base_width * scale_factor)
            # Pivot for line plot
            pivot_df = df.pivot(index='x', columns='subcategories', values='y')
            pivot_df = pivot_df[list(df['subcategories'].unique())]  # Preserve order
            # Plot (this creates its own figure)
            ax = pivot_df.plot(kind='line', marker='o', figsize=(width, height))
            # Annotate each point
            for col in pivot_df.columns:
                for i, (x_val, y_val) in enumerate(pivot_df[col].items()):
                    if pd.notna(y_val):
                        ax.annotate(f'{format_with_suffix(y_val)}',
                                    (i, y_val),
                                    textcoords="offset points",
                                    xytext=(0, 5),
                                    ha='center',
                                    fontsize=8)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
            plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='Categories')
        else:
            max_val = np.max(y)
            scale, suffix = get_suffix_scale(max_val)

            # Create DataFrame
            df = pd.DataFrame({'x': x, 'y': y})

            # Figure size scaling
            base_width = 7
            base_points = 30
            height = 4
            scale_factor = len(df) / base_points
            width = max(base_width, base_width * scale_factor)

            # Plot line chart
            plt.figure(figsize=(width, height))
            plt.plot(df['x'], df['y'], marker='o')

            # Annotate each point
            for i, (x_val, y_val) in enumerate(zip(df['x'], df['y'])):
                plt.annotate(f'{format_with_suffix(y_val)}',
                            (x_val, y_val),
                            textcoords="offset points",
                            xytext=(0, 5),
                            ha='center',
                            fontsize=8)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
        plt.xticks(rotation=90, fontsize=10)
        plt.yticks(fontsize=10)
        plt.xlabel(x_axis_label)
        plt.ylabel(f"{y_axis_label} ({suffix})")

    elif chart_type == "pie":
        # plt.pie(values, labels=categories, autopct='%1.1f%%', startangle=140)
        # Create pie chart with labels and percentages
        # Dynamic figure width
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))
        wedges, texts, autotexts = plt.pie(
            values,
            labels=categories,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'color': 'white'}
                                    )

        # Create custom legend labels with values
        legend_labels = [f"{cat}: {legend_formate(val)}" for cat, val in zip(categories, values)]

        # Add legend
        plt.legend(wedges, legend_labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0.5))

        # Ensure circle aspect ratio
        plt.axis('equal')


    elif chart_type == "waterfall":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)
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

    elif chart_type == "scatter":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(y) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(y)
        scale, suffix = get_suffix_scale(max_val)
        plt.figure(figsize=(width, height))
        plt.scatter(x, y, color='purple')
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        plt.xlabel(x_axis_label)
        plt.xticks(rotation=90, fontsize=9)
        plt.ylabel(f"{y_axis_label} ({suffix})")

    elif chart_type == "area":
        # print(f"calling from Are matplotlib tool")
        # plt.fill_between(x, y, color='lightgreen', alpha=0.7)
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)

        plt.figure(figsize=(width, height))
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

    elif chart_type == "funnel":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)
        plt.figure(figsize=(width, height))
        for i in range(len(stages)):
            plt.barh(stages[i], values[i], color='steelblue', height=0.6)

            # Create and place the label
            label = f'{format_with_suffix(values[i])}'
            plt.text(
                values[i],               # x position (end of the bar)
                stages[i],               # y position (same as bar)
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

    elif chart_type == "donut":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)
        plt.figure(figsize=(width, height))

        wedges, texts, autotexts = plt.pie(values, labels=categories, autopct='%1.1f%%', startangle=140)
        centre_circle = plt.Circle((0, 0), 0.70, fc='white')
        # Create custom legend labels with values
        legend_labels = [f"{cat}: {legend_formate(val)}" for cat, val in zip(categories, values)]

        # Add legend
        plt.legend(wedges, legend_labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0.5))
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
    elif chart_type in ["box", "box plot", 'box_plot']:
        # plt.boxplot(values, patch_artist=True, notch=True, vert=True)
        # plt.xlabel(x_axis_label)
        # plt.ylabel(y_axis_label)
        if subcategories:
            base_width = 7
            base_points = 30
            height = 4
            scale_factor = len(values) / base_points
            width = max(base_width, base_width * scale_factor)
            max_val = np.max(values)
            scale, suffix = get_suffix_scale(max_val)
            # Create DataFrame
            try:
                df = pd.DataFrame({'Subcategory': subcategories, 'Value': values})
            except: # length of values and subcategories are different
                valDf = pd.DataFrame(values, columns = ['Value'])
                subCatDf = pd.DataFrame(subcategories, columns = ['Subcategory']).drop_duplicates()
                # Repeat df2 to match length of df1
                repeats_needed = -(-len(valDf) // len(subCatDf))  # Ceiling division
                subcategory_extended = (subCatDf['Subcategory'].to_list() * repeats_needed)[:len(valDf)]
                # Create the final dataframe
                df = pd.DataFrame({
                    'Value': valDf['Value'],
                    'Subcategory': subcategory_extended
                })
            # Group by subcategory
            grouped = [df[df['Subcategory'] == cat]['Value'] for cat in df['Subcategory'].unique()]
            plt.figure(figsize=(width, height))
            plt.boxplot(grouped, labels=df['Subcategory'].unique(), patch_artist=True, notch=True, vert=True)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
        else:
            base_width = 7
            base_points = 30
            height = 4
            scale_factor = len(values) / base_points
            width = max(base_width, base_width * scale_factor)
            max_val = np.max(values)
            scale, suffix = get_suffix_scale(max_val)
            plt.figure(figsize=(width, height))
            plt.boxplot(values, patch_artist=True, notch=True, vert=True)
            formatter = FuncFormatter(dynamic_format)
            plt.gca().yaxis.set_major_formatter(formatter)
        plt.ylabel(f"{y_axis_label} ({suffix})")
        plt.xlabel(x_axis_label)
        

    elif chart_type == "bubble":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)


        df = pd.DataFrame({'x': categories, 'y': values})
        # Normalize y between 0.1 and 1
        min_norm = 0.1
        max_norm = 1.0
        y_min = df['y'].min()
        y_max = df['y'].max()
        normalized = (df['y'] - y_min) / (y_max - y_min)
        df['size'] = normalized
        df['size'] = df['size']*200
        plt.figure(figsize=(width, height))
        plt.scatter(df['x'], df['y'], s = df['size'], alpha=0.5)
        plt.xticks(df['x'])
        for i, row in df.iterrows():
            plt.text(row['x'], row['y'], f"{format_with_suffix(row['y'])}", fontsize=9, ha='center', va='center')
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)
        plt.xlabel(x_axis_label)
        plt.ylabel(f"{y_axis_label} ({suffix})")

    elif chart_type == 'heatmap':
        # Prepare DataFrame and extract labels/values
        df = pd.DataFrame({'category': categories, 'value': values})
        labels = df['category'].to_list()
        values = df['value'].to_list()
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
        fig.text(0.5, 0.3, f'Value: ${sales_val:,.0f} | Target: ${target_val:,.0f}', fontsize=12, ha='center', va='center')
        
    
    elif chart_type == "pareto":
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)
        
        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)

        df = pd.DataFrame({'category': categories, 'value': values})
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
    # elif chart_type == "stacked bar":
    elif 'stacked' in chart_type.lower():
        base_width = 7
        base_points = 30
        height = 4
        scale_factor = len(values) / base_points
        width = max(base_width, base_width * scale_factor)

        max_val = np.max(values)
        scale, suffix = get_suffix_scale(max_val)

        catDf = pd.DataFrame(categories, columns=['category']).drop_duplicates()
        subCatDf = pd.DataFrame(subcategories, columns=['subcategory']).drop_duplicates()

        # Cross-join categories and subcategories
        df = pd.merge(catDf, subCatDf, how='cross')
        df['value'] = values

        # Pivot for plotting
        pivot_df = df.pivot(index='category', columns='subcategory', values='value').fillna(0)

        # Initialize stacking bottom
        bottom = np.zeros(len(pivot_df))

        # Set figure size
        plt.figure(figsize=(width, height))

        # Plot stacked bars using pyplot
        for subcategory in pivot_df.columns:
            plt.bar(pivot_df.index, pivot_df[subcategory], bottom=bottom, label=subcategory)
            bottom += pivot_df[subcategory].values
        formatter = FuncFormatter(dynamic_format)
        plt.gca().yaxis.set_major_formatter(formatter)

        plt.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), title='Categories')
        plt.xticks(rotation=90)
        plt.xlabel(x_axis_label)
        plt.ylabel(f"{y_axis_label} ({suffix})")



    wrapped_title = "\n".join(textwrap.wrap(title, width=40))  # Wrap every ~40 characters
    plt.title(wrapped_title, fontsize=12)
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
