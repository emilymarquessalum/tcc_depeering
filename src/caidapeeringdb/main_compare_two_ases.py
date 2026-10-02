

from pathlib import Path 
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.offsetbox import AnchoredText





    
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.caidapeeringdb.main import load_timeline_data

from src.caidapeeringdb.asns import format_asn_to_search
from src.caidapeeringdb.asns import format_asn_to_search
from src.caidapeeringdb.caidapeeringdb_load import load_connections_over_time_for_asns
from src.utils.graphs import DEFAULT_FIGSIZE, format_labels_if_they_are_dates, get_colors, save_plot, sort_data_and_labels_by_total

from src.utils.graphs import save_plot


def plot_stacked_line_on_ax(
    ax,
    data_lists,
    labels,
    x_labels=None,
    title="Stacked Line Plot",
    show_title=True,
    xlabel="Index",
    ylabel="Value",
    colors=None,
    annotations=None,
    notes=None,
    max_labels=None,
    rotate_labels=False,
    sort_by_size=True,
    put_color_legend_below_y_axis=False,
    put_legend=True
):
    """Helper function to draw a stacked line plot on a specific Matplotlib Axes (ax)."""
    assert len(data_lists) > 0, "At least one data list is required"
    assert len(data_lists[0]) > 0, "Data lists cannot be empty"
    assert all(
        len(d) == len(data_lists[0]) for d in data_lists
    ), "All data lists must have the same length"
    assert len(labels) == len(
        data_lists
    ), f"Number of labels ({len(labels)}) must match data lists ({len(data_lists)})"

    # Sort data lists and labels by total if requested
    data_lists, labels = sort_data_and_labels_by_total(
        data_lists, labels, sort_by_size=sort_by_size
    )

    if x_labels is not None:
        x_labels = format_labels_if_they_are_dates(x_labels)

    labels = format_labels_if_they_are_dates(labels)

    x_indices = range(len(data_lists[0]))

    if colors is None:
        colors = get_colors()

    current_stack = [0] * len(data_lists[0])

    # Plot each layer
    for i, data_list in enumerate(data_lists):
        stacked_values = [
            current_stack[j] + data_list[j] for j in range(len(data_list))
        ]
        ax.fill_between(
            x_indices,
            current_stack,
            stacked_values,
            alpha=0.7,
            label=labels[i],
            color=colors[i % len(colors)],
        )
        ax.plot(
            x_indices,
            stacked_values,
            marker="o",
            color=colors[i % len(colors)],
            linewidth=2,
        )
        current_stack = stacked_values

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    if show_title:
        ax.set_title(title, fontsize=14)

    if put_legend:
        if put_color_legend_below_y_axis:
            ax.legend(
                loc="upper center",
                bbox_to_anchor=(0.5, -0.225 if rotate_labels else -0.15),
                ncol=min(6, len(labels)),
                fontsize=10,
            )
        else:
            ax.legend()

    ax.grid(True)
    ax.margins(x=0)

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0)

    if annotations:
        for at in annotations:
            ax.add_artist(at)

    if notes:
        at = AnchoredText(
            notes, prop=dict(size=10), frameon=True, loc="lower right"
        )
        at.patch.set_boxstyle("round,pad=0.5,rounding_size=0.5")
        ax.add_artist(at)

    # Set x-axis ticks with labels
    if x_labels is not None:
        if max_labels and len(x_labels) > max_labels:
            step = len(x_labels) // max_labels
            tick_positions = list(
                range(1, len(x_labels) - 1, step)
            )  # avoiding edges
            tick_labels = [x_labels[i] for i in tick_positions]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(
                tick_labels, rotation=45 if rotate_labels else 0,
                fontsize=10
            )
        else:
            ax.set_xticks(list(x_indices))
            ax.set_xticklabels(x_labels, rotation=45 if rotate_labels else 0,
                fontsize=10)


def plot_two_asns_side_by_side(
    asn1, asn2, data_peered, data_not_peered, subfolder=None
):
    """Creates a 1x2 figure and plots two ASNs side by side."""
    # Create side-by-side layout (1 row, 2 columns) with double default width
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(DEFAULT_FIGSIZE[0], DEFAULT_FIGSIZE[1] * 2)
    )

    asns_to_plot = [(asn1, ax1), (asn2, ax2)]

    for asn, ax in asns_to_plot:
        connections_over_time = data_peered[asn[0]]

        number_of_connections_peered = [
            len(connections) for _, connections in connections_over_time
        ]
        connections_not_peered = [
            len(connections)
            for _, connections in data_not_peered[asn[0]]
        ]
        x_dates = [file_date for file_date, _ in connections_over_time]

        plot_stacked_line_on_ax(
            ax,
            [number_of_connections_peered, connections_not_peered],
            ["In Route Server Connections", "Not-In-Route-Server Connections"],
            x_labels=x_dates,
            title=f"IXP Connections for {format_asn_to_search(asn)} over time",
            put_color_legend_below_y_axis=True,
            put_legend=asn == asn2,  
            xlabel="Date",
            ylabel="Number of Connections",
            max_labels=8,
            sort_by_size=False,
            rotate_labels=False,
        )

    plt.tight_layout()
    combined_title = f"Comparison - {format_asn_to_search(asn1)} vs {format_asn_to_search(asn2)}"
    save_plot(plt, combined_title, subfolder=subfolder)
    plt.close()


def process_and_plot_asns_in_pairs(all_files, asns_to_search_list, subfolder=None):
    """Loads connections data and generates side-by-side plots for consecutive ASN pairs."""
    connections_over_time_by_asn_peered = load_connections_over_time_for_asns(
        all_files, asns_to_search_list, connections_should_be="peered"
    )
    connections_over_time_by_asn_not_peered = load_connections_over_time_for_asns(
        all_files, asns_to_search_list, connections_should_be="not_peered"
    )

    #print(connections_over_time_by_asn_peered)
    #print(connections_over_time_by_asn_not_peered)

    # Pair ASNs sequentially (0 & 1, 2 & 3, etc.)
    for i in range(0, len(asns_to_search_list) - 1, 2):
        asn1 = asns_to_search_list[i]
        asn2 = asns_to_search_list[i + 1]

        plot_two_asns_side_by_side(
            asn1,
            asn2,
            connections_over_time_by_asn_peered,
            connections_over_time_by_asn_not_peered,
            subfolder=subfolder,
        )

if __name__ == "__main__":
    

    config_path = str(Path(__file__).parent)
    
    # Load timeline data
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering
     
    asns_to_search_list = [(15169, "Google"), (396986, "ByteDance")]  
    subfolder = "comparison_plots" 

    process_and_plot_asns_in_pairs(all_files, asns_to_search_list, subfolder=subfolder)