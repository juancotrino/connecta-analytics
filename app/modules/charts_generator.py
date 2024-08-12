import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def generate_chart(attributes_info: pd.DataFrame, font: str, marker_color: str):
    scales_spacing = 2
    scenario_spacing = 8  # Horizontal spacing between scenarios

    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(20, 6))

    unique_names = attributes_info['name'].unique()
    num_names = len(unique_names)

    # Determine unique scenarios and their count
    unique_scenarios = attributes_info['scenario'].unique()
    num_scenarios = len(unique_scenarios)

    # Calculate dynamic horizontal limits
    max_scenario_width = num_scenarios * scenario_spacing
    max_y = (num_names + 1) * scales_spacing

    # Plot each scenario side by side
    for j, scenario in enumerate(unique_scenarios):
        sub_attributes_info = attributes_info[attributes_info['scenario'] == scenario].sort_index(ascending=False).reset_index(drop=True)

        # Plot each horizontal line and the corresponding marker
        for i, attribute in sub_attributes_info.iterrows():
            y_pos = (i + 1) * scales_spacing
            x_offset = j * scenario_spacing  # Horizontal offset for each scenario

            ax.plot([1 + x_offset, 5 + x_offset], [y_pos, y_pos], color='gray', lw=6, solid_capstyle='round')  # Horizontal line
            ax.plot(attribute['value'] + x_offset, y_pos, 'o', color=marker_color, markersize=20)  # Marker

            # Place '1' and '5' at the ends of each scale bar
            ax.text(0.5 + x_offset, y_pos, '1', ha='center', va='center', fontsize=18, fontweight='bold', fontname=font)
            ax.text(5.5 + x_offset, y_pos, '5', ha='center', va='center', fontsize=18, fontweight='bold', fontname=font)

            # Place additional text aligned to the top-left of each bar and above each '5'
            ax.text(0.5 + x_offset, y_pos - 0.25, f"Nada {attribute['name']}", ha='center', va='top', fontsize=8, fontweight='bold', fontname=font, color='gray')
            ax.text(5.5 + x_offset, y_pos - 0.25, f"Muy {attribute['name']}", ha='center', va='top', fontsize=8, fontweight='bold', fontname=font, color='gray')

            # Place additional text aligned to the top-left of each bar and above each '5'
            ax.text(1 + x_offset, y_pos + 0.3, f"Prom {attribute['value']}", ha='left', va='bottom', fontsize=10, fontweight='bold', fontname=font)
            ax.text(5.5 + x_offset, y_pos + 0.5, f"Base: {attribute['base']}", ha='center', va='bottom', fontsize=8, fontweight='bold', fontname=font, color='gray')

            if not np.isnan(attribute['percentage']):
                color = '#92d050' if attribute['scenario'] == 'Atributos sensoriales en agrado' else '#e43a39'
                circle = Circle((x_offset - 0.6, y_pos), radius=0.5, color=color)
                ax.add_patch(circle)
                ax.set_aspect("equal")
                plt.text(x_offset - 0.6, y_pos, f"{int(attribute['percentage'])}%", ha='center', va='center', color='white')

        y_positions = [(i + 1) * scales_spacing for i in sub_attributes_info.index]

        # Add dashed line connecting the markers
        ax.plot(sub_attributes_info['value'] + j * scenario_spacing, y_positions, color=marker_color, linestyle='--', lw=2)

        # Add title for each scenario group
        ax.text((j * scenario_spacing) + (scenario_spacing / 2) - 1, max_y, scenario, ha='center', va='top', fontsize=14, fontweight='bold', fontname=font)

    # Add column names to the left of each scale row
    for i, name in enumerate(reversed(unique_names)):
        y_pos = (i + 1) * scales_spacing
        ax.text(-2, y_pos, name.title(), ha='center', va='center', fontsize=12, fontweight='bold', fontname=font)

    # Add title for each scenario group
    ax.text(-2, max_y, 'Atributos', ha='center', va='top', fontsize=14, fontweight='bold', fontname=font)

    # Adjust x and y limits based on number of scenarios and scales
    ax.set_xlim(-4, max_scenario_width)
    ax.set_ylim(1, max_y + 0.5)
    ax.set_xticks([])  # Hide x-axis ticks
    ax.set_yticks([])  # Hide y-axis ticks

    # Customize the plot aesthetics
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.set_facecolor('#F5F5F5')  # Light gray background

    return fig
