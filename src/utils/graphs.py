
import os
from matplotlib.offsetbox import AnchoredText
from matplotlib.patches import Patch
import numpy as np  
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
 
#import tkinter as tk
#from tkinter import ttk 
import matplotlib.patches as mpatches

from definitions import append_roots
from src.ripe_bviews.timeline.bview_vars import is_tcc_mode

#plt.style.use(['science', 'no-latex'])

import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*FigureCanvasAgg.*')

# Track graphs rendered in this session
_session_rendered_graphs = []


def clean_title_name(title):
    return title.replace(" ", "_").replace("(", "-").replace(")", "-").lower()

def save_plot(fig, title, subfolder=None):
    if not os.path.exists(starting_folder):
        os.makedirs(starting_folder)
    folder = starting_folder
    if subfolder:
        folder += subfolder + "/"
    if not os.path.exists(folder):
        os.makedirs(folder)
        with open(folder + "README.txt", "w") as f:
            f.write("This folder contains generated graphs.\n")
            f.write("Made in date: {}\n".format(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    else:
        with open(folder + "README.txt", "a") as f:
            f.write("Graph generated on: {}\n".format(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    save_fig_file = f'{folder}{clean_title_name(title)}.png'

    # windows doesnt accept saving files with >
    save_fig_file = save_fig_file.replace(">", "gt").replace("<", "lt") 
    fig.savefig(save_fig_file, bbox_inches='tight')
    print(f"Saved plot to: {save_fig_file}")
    
    # Track graph in session
    _session_rendered_graphs.append((save_fig_file, title, subfolder))


starting_folder = append_roots("graphs/")[0]

def make_sanity_check_tests(x_labels, data_list):
     
    from datetime import datetime
    
    if not x_labels or not isinstance(x_labels, (list, tuple)):
        return None
    
    # Try to parse as dates with common formats
    dates = []
    date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%m-%Y', '%d/%m/%Y', '%Y_%m_%d']
    
    for label in x_labels:
        if not isinstance(label, str):
            return None  # Not all strings, so not date labels
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(label.strip(), fmt)
                break
            except ValueError:
                continue
        
        if parsed_date is None:
            return None  # Could not parse as date
        
        dates.append(parsed_date)
    
    if len(dates) < 2:
        return None  # Need at least 2 dates to check regularity
    
    # Calculate differences between consecutive dates
    differences = []
    for i in range(1, len(dates)):
        diff = (dates[i] - dates[i-1]).days
        differences.append(diff)
    
    # Check if differences are regular (all differences should be the same)
    unique_diffs = set(differences)

     
    
    # If there's more than one unique difference value, dates are irregular
    if len(unique_diffs) > 1:
        
        max_diff_delta = max(unique_diffs) - min(unique_diffs)
        if max_diff_delta <= 3: # its just three days, so it might be a month interval
            month_diffs = set()
            for i in range(1, len(dates)):
                month_diff = (dates[i].year - dates[i-1].year) * 12 + (dates[i].month - dates[i-1].month)
                month_diffs.add(month_diff)
            
            if len(month_diffs) == 1 and month_diffs.pop() != 0:
                return # Regular non-zero monthly intervals, so not a problem
            

        text = AnchoredText("date ranges are badly configured. Unique diffs: {}".format(unique_diffs), 
                            prop=dict(size=12), 
                            frameon=True, 
                            loc='center')
        plt.gca().add_artist(text)
    return None

def plot_list_as_line_plot(data_list, y=None, title='Data Line Plot', xlabel='Index', ylabel='Value', 
                           positive_color='green', negative_color='red', subfolder=None, max_labels=None, 
                           notes=None, annotations=None, use_fill=True,
                            use_rotated_labels=False 
                           ):
    
    assert y is None or len(data_list) == len(y), "Length of data_list and y must be the same if y is provided. Lengths: data_list: {}, y: {}".format(len(data_list), len(y))
    
     
    plt.rcdefaults()
    plt.figure(figsize=(12, 6))
    x_indices = np.arange(len(data_list))  # Converted to numpy array for easier masking
    y_values = np.array(data_list)
    x_labels = list(y) if y is not None else list(x_indices)
    

    x_labels = format_labels_if_they_are_dates(x_labels)

    marker = "o" if len(data_list) <= 30 else None
     
    # Plot with conditional coloring based on positive/negative values
    if positive_color and negative_color:
        # Plot core line
        plt.plot(x_indices, y_values, marker=marker, linestyle='-', color='black', linewidth=2)
        
        if use_fill:
            # interpolate=True closes the gaps cleanly where the line crosses y=0
            plt.fill_between(x_indices, 0, y_values, where=(y_values >= 0), 
                             interpolate=True, color=positive_color, alpha=0.3)
            plt.fill_between(x_indices, 0, y_values, where=(y_values <= 0), 
                             interpolate=True, color=negative_color, alpha=0.3)
    else:
        plt.plot(x_indices, y_values, marker=marker, linestyle='-', color='orange')
    
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.margins(x=0)
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))  
 
    #make_sanity_check_tests(x_labels=y, data_list=data_list)
    
    if annotations:
        for at in annotations:
            plt.gca().add_artist(at)
            
    if notes:
        at = AnchoredText(notes, prop=dict(size=10), frameon=True, loc='lower right')
        at.patch.set_boxstyle("round,pad=0.5,rounding_size=0.5")
        plt.gca().add_artist(at)
        

    label_rotation = 45 if use_rotated_labels else 0 
    if max_labels and len(x_labels) > max_labels:
        step = len(x_labels) // max_labels 
        tick_positions = x_indices[::step]
        tick_labels = [x_labels[i] for i in range(0, len(x_labels), step)]
        plt.xticks(tick_positions, tick_labels, rotation=label_rotation)
    else: 
        plt.xticks(x_indices, x_labels, rotation=label_rotation)
        
    plt.grid()

    save_plot(plt, title, subfolder=subfolder)
    plt.close()


def plot_lists_as_plot_list_with_multiple_lines(lines_data, x_labels=None, title='Multiple Lines Plot', 
                                                xlabel='Index', ylabel='Value', subfolder=None, max_labels=None, 
                                                notes=None, annotations=None, use_rotated_labels=False):
    """
    Plots multiple lines on a single chart with customized line configurations.
    
    Args:
        lines_data (list of dicts): A list containing configuration dicts for each line.
            Example format:
            [
                {"data": [10, 12, 5], "label": "Route Server", "color": "green", "marker": "o"},
                {"data": [20, 15, 18], "label": "Bilateral", "color": "orange", "marker": "s"}
            ]
        x_labels (list): The shared timeline variables / dates for the X-axis mapping.
        title (str): Plot title.
        xlabel (str): Label for X-axis.
        ylabel (str): Label for Y-axis.
        subfolder (str): Subfolder path passed to save_plot().
        max_labels (int): Cap on the maximum number of visible ticks displayed on the X-axis.
        notes (str): Informational text blurb displayed in the bottom-right corner.
        annotations (list): Custom artist annotations to add to the plot.
        use_rotated_labels (bool): Rotates X-ticks by 45 degrees if True.
    """
    # Defensive programming: Ensure we have lines to plot and match dimensions
    assert len(lines_data) > 0, "lines_data cannot be empty."
    first_line_len = len(lines_data[0]["data"])
    for i, line in enumerate(lines_data):
        assert len(line["data"]) == first_line_len, f"Line index {i} length mismatch. Expected {first_line_len} entries."
    
    if x_labels is not None:
        assert len(x_labels) == first_line_len, f"Length of x_labels ({len(x_labels)}) must match data length ({first_line_len})."
    
    # Reset internal canvas settings
    plt.rcdefaults()
    plt.figure(figsize=(12, 6))
    
    # Generate index baselines
    x_indices = np.arange(first_line_len)
    shared_x_labels = list(x_labels) if x_labels is not None else list(x_indices)
    
    # Format dates via your local helper function
    shared_x_labels = format_labels_if_they_are_dates(shared_x_labels)

    # Automatically handle markers based on your dataset sizing rule
    default_marker = "o" if first_line_len <= 30 else None

    # --- Step 1: Sequential Line Plotting Pass ---
    for line in lines_data:
        y_values = np.array(line["data"])
        line_label = line.get("label", "")
        line_color = line.get("color", None)
        line_marker = line.get("marker", default_marker)
        line_style = line.get("linestyle", "-")
        
        # Standard plot loop utilizing parameters injected via the data dictionary
        plt.plot(x_indices, y_values, 
                 marker=line_marker, 
                 linestyle=line_style, 
                 color=line_color, 
                 linewidth=2, 
                 label=line_label)


    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.margins(x=0)

    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))  
    plt.ylim(top=max(max(line["data"]) for line in lines_data) * 1.1)  # Add 10% headroom to the top of the Y-axis
    # Inject third-party matplotlib artist layers if present
    if annotations:
        for at in annotations:
            plt.gca().add_artist(at)
            
    # Inject summary notes
    if notes:
        at = AnchoredText(notes, prop=dict(size=10), frameon=True, loc='lower right')
        at.patch.set_boxstyle("round,pad=0.5,rounding_size=0.5")
        plt.gca().add_artist(at)
        
    # Process Tick Rotations and Decimation steps
    label_rotation = 45 if use_rotated_labels else 0 
    if max_labels and len(shared_x_labels) > max_labels:
        step = len(shared_x_labels) // max_labels 
        tick_positions = x_indices[::step]
        tick_labels = [shared_x_labels[i] for i in range(0, len(shared_x_labels), step)]
        plt.xticks(tick_positions, tick_labels, rotation=label_rotation)
    else: 
        plt.xticks(x_indices, shared_x_labels, rotation=label_rotation)
        
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc="upper left")  # Added to separate multiple metric identities clearly
    plt.tight_layout()

    # Save and terminate canvas sequence safely
    save_plot(plt, title, subfolder=subfolder)
    plt.close()

    
def plot_map_as_bar_plot(data_map, title='Data Bar Plot', xlabel='Key', ylabel='Value', subfolder=None, max_x_value=None, max_labels=None, use_colors=False, 
                         colors=None,
                         is_percentage=False,
                         sort_by_size=False,
                         sort_by_size_cut=None,
                         use_rotated_labels=True):
    keys = list(data_map.keys())
    keys = sorted(keys)
    values = [data_map[key] for key in keys]
    
    # order it by new key ordered after sorting
    if colors: 
        colors = [colors[key] for key in keys]

    plot_list_as_bar_plot(keys, y=values, title=title, xlabel=xlabel, ylabel=ylabel,
                          is_percentage=is_percentage,
                          sort_by_size=sort_by_size,
                          sort_by_size_cut=sort_by_size_cut,
                          colors=colors if colors else get_negative_positive_colors(keys) if type(keys[0]) == float else None,
                           subfolder=subfolder, max_x_value=max_x_value, max_labels=max_labels, use_colors=use_colors, use_rotated_labels=use_rotated_labels)
def _prepare_and_filter_data(data_list, y, colors, data_annotated_values, use_colors, do_top_n, sort_by_size, sort_by_size_cut):
    """Handles sorting, top-n filtering, and default coloring."""
    # 1. Unify: If y is missing, data_list is actually the values, and labels are indices
    if y is None:
        y_values = list(data_list)
        x_labels = list(range(len(data_list)))
    else:
        y_values = list(y)
        x_labels = list(data_list)

    # 2. Defaults
    if colors is None:
        colors = get_colors() if use_colors else ['lightgreen'] * len(y_values)
    ann_values = list(data_annotated_values) if data_annotated_values is not None else [None] * len(y_values)

    # 3. Zip together to keep parallel state synced during transformations
    items = [{'x': x, 'y': v, 'c': c, 'a': a} for x, v, c, a in zip(x_labels, y_values, colors, ann_values)]

    # 4. Apply Filters / Sorting
    if do_top_n and y is not None:
        items = sorted(items, key=lambda i: i['y'], reverse=True)[:do_top_n]
    elif sort_by_size and y is not None:
        items = sorted(items, key=lambda i: i['y'], reverse=True)
        if sort_by_size_cut and sort_by_size_cut < len(items):
            items = items[:sort_by_size_cut]

    return items


def _apply_max_x_cap(items, max_x_value):
    """Collapses items above max_x_value into a single trailing bar."""
    over_x_items = [item for item in items if isinstance(item['x'], (int, float)) and item['x'] >= max_x_value]
    if not over_x_items:
        return items

    start_index = len(items) - len(over_x_items)
    base_items = items[:start_index]

    # Aggregate the overflow
    over_x_value = sum(item['y'] for item in over_x_items)
    
    try:
        over_x_ann = sum(item['a'] for item in over_x_items if item['a'] is not None)
    except TypeError:
        over_x_ann = "..."

    base_items.append({
        'x': f'>{max_x_value}',
        'y': over_x_value,
        'c': over_x_items[0]['c'], # keep color of the first overflow item
        'a': over_x_ann
    })
    return base_items


def _get_shifted_positions(length, separations):
    """Calculates x-positions with gaps added at separation moments."""
    if not separations:
        return list(range(length)), []
    
    x_positions = []
    for i in range(length):
        offset = sum(1 for sep in separations if i >= sep)
        x_positions.append(i + offset)
        
    adjusted_seps = []
    for sep in separations:
        offset = sum(1 for s in separations if sep > s)
        adjusted_seps.append(sep + offset - 0.5)
        
    return x_positions, adjusted_seps

 
def plot_list_as_bar_plot(data_list, y=None, data_annotated_values=None,
                          extra_labels=None,
                          title='Data Bar Plot', xlabel='Index', ylabel='Value', subfolder=None, 
                          max_x_value=None, max_labels=None, use_colors=False, colors=None, 
                          color_labels=None, is_percentage=False, do_top_n=None, sort_by_size=False,
                          sort_by_size_cut=None, range_of_bar_group_subdivisions=None, use_rotated_labels=False):
    
    plt.rcdefaults()
    plt.figure(figsize=(12, 6))
    
    # Assertions
    assert y is None or len(data_list) == len(y), f"Length mismatch: data_list ({len(data_list)}) != y ({len(y)})"
    if data_annotated_values is not None:
        assert len(data_annotated_values) == len(data_list), "Length of data_annotated_values must match data_list."
    if extra_labels is not None:
        assert len(extra_labels) == len(data_list), "Length of extra_labels must match data_list."

    # Process & Clean Data State
    # Note: If your internal `_prepare_and_filter_data` function doesn't automatically handle `extra_labels`,
    # we can zip them here or ensure they match indices after filtering. 
    # Assuming standard behavior, we map extra_labels tracking by indexing the original data_list structure:
    items = _prepare_and_filter_data(data_list, y, colors, data_annotated_values, use_colors, do_top_n, sort_by_size, sort_by_size_cut)
    
    if y is not None and max_x_value is not None:
        items = _apply_max_x_cap(items, max_x_value)

    # Calculate Coordinates
    x_positions, adjusted_seps = _get_shifted_positions(len(items), range_of_bar_group_subdivisions)
    y_values = [item['y'] for item in items]
    x_labels = [item['x'] for item in items]
    plot_colors = [item['c'] for item in items]

    # Handle Extra Labels Processing (mapping back to filtered items if necessary)
    if extra_labels is not None:
        # Create a lookup mapping from original data_list elements to their extra labels
        # (This protects integrity if _prepare_and_filter_data sorts or filters items)
        label_lookup = {orig_x: extra for orig_x, extra in zip(data_list, extra_labels)}
        
        # Combine the original x_label with the extra label using a newline
        x_labels = [f"{x}\n{label_lookup.get(x, '')}" for x in x_labels]

    # Draw Bars
    bars = plt.bar(x_positions, y_values, color=plot_colors)
    
    # Handle X Ticks & Labels 
    if max_labels and len(items) > max_labels:
        step = len(items) // max_labels
        tick_positions = x_positions[::step]
        tick_labels = x_labels[::step]
        plt.xticks(tick_positions, tick_labels, rotation=45 if use_rotated_labels else 0)
    else:
        plt.xticks(x_positions, x_labels, rotation=45 if use_rotated_labels else 0)

    # Add Annotations
    if data_annotated_values is not None:
        for bar, item in zip(bars, items):
            if item['a'] is None: continue
            height = bar.get_height()
            va_dir = 'bottom' if height >= 0 else 'top'
            offset = 3 if height >= 0 else -3
            
            plt.annotate(
                f"{item['a']}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, offset),
                textcoords="offset points",
                ha='center', va=va_dir, fontsize=9
            )

    # Draw Separation Lines
    for sep_pos in adjusted_seps:
        plt.axvline(x=sep_pos, color='gray', linestyle='--', linewidth=1)

    # Formatting & Styling
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if not is_tcc_mode():
        plt.title(title)
        
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    if is_percentage:
        plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda val, _: f'{val:.0%}'))
    plt.grid(axis='y') 
 
    # Legend
    if color_labels:
        color_label_mapping = {color: label for label, color in color_labels.items()}
        legend_patches = [mpatches.Patch(color=c, label=l) for l,c in color_label_mapping.items()]
        plt.legend(handles=legend_patches, loc='best') 
 
    save_plot(plt, title, subfolder=subfolder)
    plt.close()

def plot_list_as_heat_map(data: list[list[float]], title='Heat Map', x_labels=None, y_labels=None, subfolder=None):
    plt.figure(figsize=(10, 8))
    #plt.imshow(data, cmap='viridis', aspect='auto')
    plt.imshow(data, cmap='viridis', aspect='auto', origin='lower')
    plt.colorbar(label='Value')
    
    if x_labels is not None:
        plt.xticks(range(len(x_labels)), x_labels, rotation=45)
    if y_labels is not None:
        plt.yticks(range(len(y_labels)), y_labels)
    
    for i in range(len(y_labels)):
        for j in range(len(x_labels)):
            is_high = data[i][j] >= (max(max(row) for row in data) * 0.75)  # Adjust threshold as needed
            color = 'black' if is_high else 'white'
            plt.text(j, i, str(data[i][j]), ha='center', va='center', color=color, fontsize=12)
    
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    plt.title(title)
    plt.grid(False)

    save_plot(plt, title, subfolder=subfolder)
    plt.close()

def get_colors():
    return ['orange', 'lightblue', 'lightgreen', 'red', 'purple', 'cyan', 'magenta', 'yellow', 'brown', 'pink',
                    'gray', 'olive', 'teal', 'navy', 'maroon', 'lime', 'coral', 'gold', 'indigo', 'violet',
                    'salmon', 'turquoise', 'tan', 'orchid', 'plum', 'steelblue', 'sandybrown', 'lightcoral', 'mediumseagreen', 'mediumpurple'
                  ]

def create_colors_for_groups(groups: list[str],
    overrides:dict[str,str]=None
) -> tuple[list[str], dict[str, str]]:
    unique_groups = list(set(groups)) 
    color_palette = get_colors()
    if overrides:
        color_palette = [color  for color in color_palette if color not in overrides.values()]
    group_to_color = {group: color_palette[i % len(color_palette)] for i, group in enumerate(unique_groups)}
    color_to_group = {color: group for group, color in group_to_color.items()}
    if overrides:
        for g,c in overrides.items():
            color_to_group[c] = g
            group_to_color[g] = c
    return [group_to_color[group] for group in groups], color_to_group

def get_negative_positive_colors(categories: list[int]):

    most_relevant_positive_category = max([cat for cat in categories if cat > 0], default=None)
    most_relevant_negative_category = min([cat for cat in categories if cat < 0], default=None)

    colors = []
    for cat in categories: 
        if cat > 0 and most_relevant_positive_category is not None:
            intensity = cat / most_relevant_positive_category
            # Interpolate from pale green to dark green
            r = 0.5 * (1 - intensity)
            g = 1 - 0.4 * intensity
            b = 0.5 * (1 - intensity)
            colors.append((r, g, b))
        elif cat < 0 and most_relevant_negative_category is not None:
            intensity = abs(cat) / abs(most_relevant_negative_category)
            # Interpolate from pale red to dark red
            r = 1 - 0.4 * intensity
            g = 0.5 * (1 - intensity)
            b = 0.5 * (1 - intensity)
            colors.append((r, g, b))
        else:
            colors.append((0.8, 0.8, 0.8))  # Neutral color for zero
    return colors

def sort_data_and_labels_by_total(data_lists, labels, sort_by_size=True):
    """
    Sort data lists and their corresponding labels by the total sum of each data list.
    
    Args:
        data_lists: List of data lists (each is a list of numbers)
        labels: List of labels corresponding to each data list
        sort_by_size: If True, sort by total sum (descending). If False, return original order.
    
    Returns:
        Tuple of (sorted_data_lists, sorted_labels)
    """
    if not sort_by_size:
        return data_lists, labels
    
    # Calculate totals and create indices
    totals = [sum(data_list) for data_list in data_lists]
    sorted_indices = sorted(range(len(data_lists)), key=lambda i: totals[i], reverse=True)
    
    # Reorder
    sorted_data_lists = [data_lists[i] for i in sorted_indices]
    sorted_labels = [labels[i] for i in sorted_indices]
    
    return sorted_data_lists, sorted_labels


def format_labels_if_they_are_dates(labels):

    if len(labels) == 0:
        return labels
    
    first_label = labels[0]

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    if isinstance(first_label, str):
        try:
            # Try parsing the first label as a date
            from dateutil import parser
            parser.parse(first_label.replace("_", "-").strip())  
            # If parsing succeeds, format all labels as dates
            formatted_labels = []
            label_dates = []
            for label in labels:
                date = parser.parse(label.replace("_", "-").strip())
                label_dates.append(date) 
            
            all_dates_have_same_day = True#all(date.day == label_dates[0].day for date in label_dates)

            for date in label_dates:
                month_str = months[date.month - 1]  # Get month name from month number

                day_text = ""
                if not all_dates_have_same_day:
                    
                    if 11 <= date.day <= 13: 
                        suffix = "th"
                    else:
                        suffix = {1: "st", 2: "nd", 3: "rd"}.get(date.day % 10, "th")
                    
                    day_text = f"{date.day}{suffix} of "
                    
                formatted_labels.append(date.strftime('%Y, ') + 
                                            day_text + 
                                            month_str
                                            ) 
            return formatted_labels
        except (ValueError, TypeError) as e:
            #print("Couldnt parse because: ", e)
            return labels  # Not date strings, return original labels

    return labels  

def plot_stacked_bar_plot(data_lists, labels, x_labels=None, title='Stacked Bar Plot', xlabel='Index', ylabel='Value', colors=None, subfolder=None, annotations=None, notes=None, max_labels=None, sort_by_size=False, is_percentage=False, use_rotated_labels=True):
    """
    Create a stacked bar plot from multiple data lists.
    
    Args:
        data_lists: List of data lists (each is a list of numbers)
        labels: List of labels corresponding to each data list
        x_labels: Labels for the x-axis (if None, uses indices)
        title: Title of the plot
        xlabel: Label for x-axis
        ylabel: Label for y-axis
        colors: List of colors for each data list (if None, auto-generated)
        subfolder: Subfolder to save the plot in
        annotations: List of annotations to add to the plot
        notes: Notes to display on the plot
        max_labels: Maximum number of x-axis labels to display
        sort_by_size: If True, sort data lists by total sum (descending)
        is_percentage: If True, format y-axis as percentages
        use_rotated_labels: If True, rotate x-axis labels 45 degrees
    """
    assert len(data_lists) > 0, "At least one data list is required"
    assert len(data_lists[0]) > 0, "Data lists cannot be empty"
    assert all(len(data_list) == len(data_lists[0]) for data_list in data_lists), "All data lists must have the same length"
    assert len(labels) == len(data_lists), "Number of labels must match number of data lists. Got {} labels and {} data lists".format(len(labels), len(data_lists))
    assert colors is None or len(colors) >= len(data_lists), "If colors are provided, there must be at least as many colors as data lists"
    assert x_labels is None or len(x_labels) == len(data_lists[0]), "If x_labels are provided, their length, which is {}, must match the length of data lists, which is {}".format(len(x_labels) if x_labels else 0, len(data_lists[0]))

    # Sort data lists and labels by total if requested
    data_lists, labels = sort_data_and_labels_by_total(data_lists, labels, sort_by_size=sort_by_size)

    plt.figure(figsize=(12, 6))
    
    # If sort_by_size, sort the x-axis bars by their total height
    if sort_by_size:
        # Calculate total for each x position (sum across all layers)
        x_totals = [sum(data_lists[i][j] for i in range(len(data_lists))) for j in range(len(data_lists[0]))]
        # Get indices sorted by total (descending)
        sorted_x_indices_original = sorted(range(len(x_totals)), key=lambda i: x_totals[i], reverse=True)
        # Reorder all data_lists to match the sorted x-axis order
        data_lists = [[data_lists[i][j] for j in sorted_x_indices_original] for i in range(len(data_lists))]
        # Also reorder x_labels if provided
        if x_labels is not None:
            x_labels = [x_labels[j] for j in sorted_x_indices_original]
    
    x_indices = range(len(data_lists[0]))
    
    if colors is None:
        colors = get_colors()
    
    # Create stacked bars
    current_stack = [0] * len(data_lists[0])
    
    for i, data_list in enumerate(data_lists):
        stacked_values = [current_stack[j] + data_list[j] for j in range(len(data_list))]
        plt.bar(x_indices, data_list, bottom=current_stack, label=labels[i], color=colors[i % len(colors)], alpha=0.8)
        current_stack = stacked_values
    
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    plt.grid(axis='y')
    plt.margins(x=0)
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    
    if is_percentage:
        plt.ylim(0, 100)
    
    if annotations:
        for at in annotations:
            plt.gca().add_artist(at)
    
    if notes:
        at = AnchoredText(notes, prop=dict(size=10), frameon=True, loc='lower right')
        at.patch.set_boxstyle("round,pad=0.5,rounding_size=0.5")
        plt.gca().add_artist(at)

    make_sanity_check_tests(x_labels=x_labels, data_list=data_lists[0])   
    
    # Set x-axis ticks with labels
    if x_labels is not None:
        if max_labels and len(x_labels) > max_labels:
            step = len(x_labels) // max_labels
            tick_positions = list(range(0, len(x_labels), step))
            tick_labels = [x_labels[i] for i in tick_positions]
            plt.xticks(tick_positions, tick_labels, rotation=45 if use_rotated_labels else 0)
        else:
            plt.xticks(list(x_indices), x_labels, rotation=45 if use_rotated_labels else 0)
    else:
        if max_labels and len(x_indices) > max_labels:
            step = len(x_indices) // max_labels
            tick_positions = list(range(0, len(x_indices), step))
            plt.xticks(tick_positions, rotation=45 if use_rotated_labels else 0)
    
    if is_percentage:
        ax = plt.gca()
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: '{:.0%}'.format(y)))

    plt.tight_layout()
    save_plot(plt, title, subfolder=subfolder)
    plt.close()

def plot_stacked_line_plot(data_lists, labels, x_labels=None, title='Stacked Line Plot',
                           show_title=True, xlabel='Index', ylabel='Value', colors=None, 
                           subfolder=None, annotations=None, notes=None, max_labels=None, 
                           rotate_labels=True,
                           sort_by_size=True, put_color_legend_below_y_axis=False): 
    
    assert len(data_lists) > 0, "At least one data list is required"
    assert len(data_lists[0]) > 0, "Data lists cannot be empty"
    assert all(len(data_list) == len(data_lists[0]) for data_list in data_lists), "All data lists must have the same length"
    assert len(labels) == len(data_lists), "Number of labels must match number of data lists. Got {} labels and {} data lists and {} x_labels.".format(len(labels), len(data_lists), len(x_labels) if x_labels is not None else 0)
    assert colors is None or len(colors) >= len(data_lists), "If colors are provided, there must be at least as many colors as data lists"
    assert x_labels is None or len(x_labels) == len(data_lists[0]), "If x_labels are provided, their length, which is {}, must match the length of data lists, which is {}".format(len(x_labels), len(data_lists[0]))

    # Sort data lists and labels by total if requested
    data_lists, labels = sort_data_and_labels_by_total(data_lists, labels, sort_by_size=sort_by_size)
    
    if x_labels is not None:
        x_labels = format_labels_if_they_are_dates(x_labels)
    
    labels = format_labels_if_they_are_dates(labels)

    plt.figure(figsize=(12, 6))
    x_indices = range(len(data_lists[0]))
    
    if colors is None:
        colors = get_colors()
     
    current_stack = [0] * len(data_lists[0])
    
    for i, data_list in enumerate(data_lists):
        stacked_values = [current_stack[j] + data_list[j] for j in range(len(data_list))]
        plt.fill_between(x_indices, current_stack, stacked_values, alpha=0.7, label=labels[i], color=colors[i % len(colors)])
        plt.plot(x_indices, stacked_values, marker='o', color=colors[i % len(colors)], linewidth=2)
        current_stack = stacked_values
    
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if show_title:
        plt.title(title)
         
    if put_color_legend_below_y_axis: 
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.225 if rotate_labels else -0.08), ncol=min(6, len(labels)))
    else:
        plt.legend() 
        
    plt.grid()
    plt.margins(x=0)
     
    ax = plt.gca()

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))  
    ax.set_ylim(bottom=0)  # Ensure y-axis starts at 0
    
    if annotations:
        for at in (annotations):
            plt.gca().add_artist(at)
    
    if notes:
        at = AnchoredText(notes, prop=dict(size=10), frameon=True, loc='lower right')
        at.patch.set_boxstyle("round,pad=0.5,rounding_size=0.5")
        plt.gca().add_artist(at)
    
    # Set x-axis ticks with labels
    if x_labels is not None:
        if max_labels and len(x_labels) > max_labels:
            step = len(x_labels) // max_labels 
            tick_positions = list(range(1, len(x_labels) - 1, step)) # avoiding the edges
            tick_labels = [x_labels[i] for i in tick_positions]
            plt.xticks(tick_positions, tick_labels, rotation=45 if rotate_labels else 0)
        else:
            plt.xticks(list(x_indices), x_labels, rotation=45 if rotate_labels else 0)
     
    # Automatically adjust subplot parameters so the legend fits in the saved image
    plt.tight_layout() 
     
    save_plot(plt, title, subfolder=subfolder)
    plt.close()


def plot_list_as_win_loss_bar_plot(list_to_plot, title, y=None, xlabel='Index', ylabel='Gain/Loss', subfolder=None, max_labels=None,
                                   create_text_report=False):
    
    win_and_losses_over_time = []
    item_win_and_losses_over_time = []

    for i in range(1, len(list_to_plot)):
        first_items = list_to_plot[i-1]
        second_items = list_to_plot[i]
        gain_items = set(second_items) - set(first_items)
        loss_items = set(first_items) - set(second_items)
        gain = len(gain_items)
        loss = len(loss_items)
        win_and_losses_over_time.append((gain, loss))
        item_win_and_losses_over_time.append((gain_items, loss_items))

    gains = [gain for gain, loss in win_and_losses_over_time]
    losses = [loss for gain, loss in win_and_losses_over_time]
    
    plt.figure(figsize=(12, 6))
    
    x_indices = list(range(len(gains)))
    bar_width = 0.35
    
    # Create bars for gains and losses side by side
    bars1 = plt.bar([x - bar_width/2 for x in x_indices], gains, bar_width, label='Gains', color='green', alpha=0.7)
    bars2 = plt.bar([x + bar_width/2 for x in x_indices], losses, bar_width, label='Losses', color='red', alpha=0.7)
    
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(axis='y')
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    
    # Handle x-axis labels
    if max_labels and len(x_indices) > max_labels:
        step = len(x_indices) // max_labels
        tick_positions = [x_indices[i] for i in range(0, len(x_indices), step)]
        tick_labels = y if y else [str(i) for i in range(0, len(x_indices), step)]
        plt.xticks(tick_positions, tick_labels)
    else:
        plt.xticks(x_indices, y if y else [str(i) for i in range(len(x_indices))])
    
    save_plot(plt, title, subfolder=subfolder)

    if create_text_report:
        report_path = os.path.join(starting_folder, subfolder if subfolder else "", f"{title.replace(' ', '_').lower()}_report.txt")
        with open(report_path, "w") as f:
            f.write(f"Report for {title}\n")
            f.write(f"Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Gains and Losses Over Time:\n")
            for i, (gain, loss) in enumerate(win_and_losses_over_time):
                label = y[i] if y and i < len(y) else str(i)
                f.write(f"{label}:\n")
                f.write(f"\nGains: {gain}\n")
                f.write("".join((f"{item}\n" for item in item_win_and_losses_over_time[i][0])))
                f.write(f"\nLosses: {loss}\n")
                f.write("".join((f"{item}\n" for item in item_win_and_losses_over_time[i][1])))
                f.write("\n")
        print(f"Saved text report to: {report_path}")

    plt.close()  
    

def plot_stacked_win_loss_bar_plot_by_continent(continent_connections_over_time, title, y=None, xlabel='Index', ylabel='Gain/Loss', subfolder=None, max_labels=None, create_text_report=False, sort_by_size=True):


    # Extract continents from the data in order of first appearance
    all_continents = set()
    sorted_continents = []
    for _, continent_connections in continent_connections_over_time:
        for continent in continent_connections.keys():
            if continent not in all_continents:
                all_continents.add(continent)
                sorted_continents.append(continent)
    
    # Calculate gains and losses per continent over time
    continent_gains = {continent: [] for continent in sorted_continents}
    continent_gains_items = {continent: [] for continent in sorted_continents}
    continent_losses = {continent: [] for continent in sorted_continents}
    continent_losses_items = {continent: [] for continent in sorted_continents}
    
    for time_idx in range(1, len(continent_connections_over_time)):
        prev_date, prev_continent_conns = continent_connections_over_time[time_idx - 1]
        curr_date, curr_continent_conns = continent_connections_over_time[time_idx]
        
        # For each continent, calculate gains and losses
        for continent in sorted_continents:
            prev_items = prev_continent_conns.get(continent, [])
            curr_items = curr_continent_conns.get(continent, [])

            # Get all unique IDs and names from previous and current snapshots
            prev_ids = {str(conn.get("id")) for conn in prev_items}
            prev_names = {conn.get("name", "Unknown") for conn in prev_items}
            curr_ids = {str(conn.get("id")) for conn in curr_items}
            curr_names = {conn.get("name", "Unknown") for conn in curr_items}
            
            # An item is a gain if BOTH its ID is new AND its name is new
            # (i.e., it doesn't match on either ID or name from previous snapshot)
            gain_items = []
            for conn in curr_items:
                id_ = str(conn.get("id"))
                name = conn.get("name", "Unknown")
                if id_ not in prev_ids and name not in prev_names:
                    gain_items.append((id_, name))
            
            # An item is a loss if BOTH its ID is gone AND its name is gone
            # (i.e., it doesn't match on either ID or name in current snapshot)
            loss_items = []
            for conn in prev_items:
                id_ = str(conn.get("id"))
                name = conn.get("name", "Unknown")
                if id_ not in curr_ids and name not in curr_names:
                    loss_items.append((id_, name))
            
            # Remove duplicates (same ID-name pair)
            gain_items = list(set(gain_items))
            loss_items = list(set(loss_items))
            
            # Store items and counts
            continent_gains_items[continent].append(gain_items)
            continent_losses_items[continent].append(loss_items)
            continent_gains[continent].append(len(gain_items))
            continent_losses[continent].append(len(loss_items))
    
    # Sort continents by size (total gains + losses) if requested
    if sort_by_size:
        continent_totals = {continent: sum(continent_gains[continent]) - sum(continent_losses[continent]) for continent in sorted_continents}
        sorted_continents = sorted(sorted_continents, key=lambda c: abs(continent_totals[c]), reverse=True)
    num_time_periods = len(continent_connections_over_time) - 1
    x_indices = list(range(num_time_periods))
    
    plt.figure(figsize=(14, 7))
    
    colors = get_colors()
    bar_width = 0.35
    
    # Stack gains on the positive side
    gains_stack = [0] * num_time_periods
    continent_colors = {}
    for i, continent in enumerate(sorted_continents):
        gains_data = continent_gains[continent]
        color = colors[i % len(colors)]
        continent_colors[continent] = color
        plt.bar(
            [x - bar_width/2 for x in x_indices],
            gains_data,
            bar_width,
            bottom=gains_stack,
            color=color,
            alpha=0.7
        )
        gains_stack = [gains_stack[j] + gains_data[j] for j in range(num_time_periods)]
    
    # Stack losses on the negative side
    losses_stack = [0] * num_time_periods
    for i, continent in enumerate(sorted_continents):
        losses_data = continent_losses[continent]
        color = continent_colors[continent]
        plt.bar(
            [x + bar_width/2 for x in x_indices],
            [-loss for loss in losses_data],  # Negative for losses
            bar_width,
            bottom=losses_stack,
            color=color,
            alpha=0.7,
            hatch='//'
        )
        losses_stack = [losses_stack[j] - losses_data[j] for j in range(num_time_periods)]
    
    # Create custom legend with continents and gains/losses indicators
    continent_patches = [Patch(facecolor=continent_colors[continent], alpha=0.7, label=continent) 
                         for continent in sorted_continents]
    gains_patch = Patch(facecolor='lightgray', alpha=0.7, label='Gains')
    losses_patch = Patch(facecolor='lightgray', alpha=0.7, hatch='//', label='Losses')
    
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    
    # Create legend with two rows: continents first, then gains/losses
    all_patches = continent_patches + [gains_patch, losses_patch]
    plt.legend(handles=all_patches, loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
    plt.grid(axis='y')
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    
    # Handle x-axis labels
    if max_labels and len(x_indices) > max_labels:
        step = len(x_indices) // max_labels
        tick_positions = [x_indices[i] for i in range(0, len(x_indices), step)]
        tick_labels = [y[i] if y else str(i) for i in range(0, len(x_indices), step)]
        plt.xticks(tick_positions, tick_labels, rotation=45)
    else:
        plt.xticks(x_indices, y if y else [str(i) for i in range(num_time_periods)], rotation=45)
    
    plt.tight_layout()
    save_plot(plt, title, subfolder=subfolder)
    
    if create_text_report:
        report_path = os.path.join(starting_folder, subfolder if subfolder else "", f"{title.replace(' ', '_').replace('(', '').replace(')', '').lower()}_report.txt")
        with open(report_path, "w") as f:
            f.write(f"Report for {title}\n")
            f.write(f"Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Gains and Losses by Continent Over Time:\n\n")
            for time_idx in range(num_time_periods):
                label = y[time_idx] if y else f"Period {time_idx}"
                f.write(f"{label}:\n")
                for continent in sorted_continents:
                    f.write(f"  {continent}:\n")
                    f.write(f"    Gains: {continent_gains[continent][time_idx]}\n")
                    for id_, name in continent_gains_items[continent][time_idx]:
                        f.write(f"      ID {id_}: {name}\n")
                    f.write(f"    Losses: {continent_losses[continent][time_idx]}\n")
                    for id_, name in continent_losses_items[continent][time_idx]:
                        f.write(f"      ID {id_}: {name}\n")
                f.write("\n") 
        print(f"Saved text report to: {report_path}")
    
    plt.close()


    return continent_colors

def create_window_with_all_rendered_graphs_this_session():
    pass

"""
def create_window_with_all_rendered_graphs_this_session():
 
    if not _session_rendered_graphs:
        print("No graphs rendered in this session.")
        return
    
    num_graphs = len(_session_rendered_graphs)
    
    # Calculate grid dimensions
    cols = 2  # 2 columns for better viewing
    rows = (num_graphs + cols - 1) // cols  # Ceiling division
    
    # Create root window
    root = tk.Tk()
    root.title("Rendered Graphs - This Session")
    root.geometry("1400x900")
    
    # Create main frame for scrollbars
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create canvas
    canvas = tk.Canvas(main_frame, bg='white')
    
    # Create scrollbars
    v_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    h_scrollbar = ttk.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)
    
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Enable mouse wheel scrolling (cross-platform)
    def _on_mousewheel(event):
        if event.num == 5 or event.delta < 0:  # Scroll down
            canvas.yview_scroll(3, "units")
        elif event.num == 4 or event.delta > 0:  # Scroll up
            canvas.yview_scroll(-3, "units")
    
    def _on_shift_mousewheel(event):
        if event.num == 5 or event.delta < 0:  # Scroll right
            canvas.xview_scroll(3, "units")
        elif event.num == 4 or event.delta > 0:  # Scroll left
            canvas.xview_scroll(-3, "units")
    
    # Bind mouse wheel events (Windows/Mac style)
    canvas.bind("<MouseWheel>", _on_mousewheel)
    scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
    
    # Bind mouse wheel events (Linux style)
    canvas.bind("<Button-4>", _on_mousewheel)
    canvas.bind("<Button-5>", _on_mousewheel)
    scrollable_frame.bind("<Button-4>", _on_mousewheel)
    scrollable_frame.bind("<Button-5>", _on_mousewheel)
    
    # Bind shift+mouse wheel for horizontal scrolling
    canvas.bind("<Shift-MouseWheel>", _on_shift_mousewheel)
    scrollable_frame.bind("<Shift-MouseWheel>", _on_shift_mousewheel)
    
    # Also bind to all child widgets for better coverage
    def _bind_mousewheel_recursive(widget):
        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)
        widget.bind("<Shift-MouseWheel>", _on_shift_mousewheel)
        for child in widget.winfo_children():
            _bind_mousewheel_recursive(child)
    
    _bind_mousewheel_recursive(scrollable_frame)
    
    # Create grid of graphs
    graph_index = 0
    for row in range(rows):
        for col in range(cols):
            if graph_index >= num_graphs:
                break
             
            graph_path, title, subfolder = _session_rendered_graphs[graph_index]
            
            # Create frame for each graph
            graph_frame = ttk.LabelFrame(scrollable_frame, text=title, padding=5)
            graph_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            if os.path.exists(graph_path):
                try:
                    # Load image
                    img = Image.open(graph_path)
                    
                    # Resize to fit grid (approximately 650x500 per cell for 2 columns)
                    max_width = 650
                    max_height = 500
                    ratio = min(max_width / img.width, max_height / img.height)
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    photo = ImageTk.PhotoImage(img_resized)
                    
                    # Create label with image
                    img_label = tk.Label(graph_frame, image=photo, bg='white')
                    img_label.image = photo  # Keep a reference
                    img_label.pack()
                    
                except Exception as e:
                    error_label = tk.Label(graph_frame, text=f"Error loading:\n{str(e)}", 
                                          fg='red', bg='white', wraplength=600)
                    error_label.pack()
            else:
                error_label = tk.Label(graph_frame, text="File not found", 
                                      fg='red', bg='white')
                error_label.pack()
            
            graph_index += 1
    
    # Grid layout for canvas and scrollbars
    canvas.grid(row=0, column=0, sticky="nsew")
    v_scrollbar.grid(row=0, column=1, sticky="ns")
    h_scrollbar.grid(row=1, column=0, sticky="ew")
    
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    
    # Add title label
    title_label = ttk.Label(root, text=f"All Rendered Graphs - This Session ({num_graphs} total) | Scroll: Mouse Wheel (vertical), Shift+Wheel (horizontal)", 
                           font=("Arial", 10))
    title_label.pack(side=tk.TOP, padx=5, pady=5)
    
    root.mainloop()
"""


def create_text_bubble(
    lines, 
    background="#ffffff", 
    text_color="#000000", 
    font_size=24, 
    underline_wrapping=None, 
    subfolder=None,
    output_filename="text_bubble.png"
):
    pass

def plot_cdf(data, title='Empirical CDF', xlabel='Value', ylabel='Cumulative Probability', subfolder=None, color='navy', notes=None, annotations=None):
    
    if not data or len(data) == 0:
        print("Warning: Empty data array passed to plot_cdf(). Skipping plot.")
        return

    plt.rcdefaults()
    plt.figure(figsize=(10, 6))

    # Sort data and compute CDF values (Y-axis: 0.0 to 1.0 or 0% to 100%)
    sorted_data = np.sort(data)
    y_vals = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

    # Plot step function for proper ECDF visualization
    plt.step(sorted_data, y_vals, where='post', color=color, linewidth=2, label='ECDF')
    plt.plot(sorted_data, y_vals, 'o', color=color, alpha=0.3, markersize=4)  # Data point markers

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if not is_tcc_mode():
        plt.title(title)

    plt.ylim(0, 1.05)
    plt.xlim(left=0)
    plt.grid(True, linestyle=':', alpha=0.6)

    # Format Y-axis as percentage
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda val, _: f'{val:.0%}'))

    # Optional annotations and notes
    if annotations:
        for at in annotations:
            plt.gca().add_artist(at)

    if notes:
        at = AnchoredText(notes, prop=dict(size=10), frameon=True, loc='lower right')
        at.patch.set_boxstyle("round,pad=0.5,rounding_size=0.5")
        plt.gca().add_artist(at)

    plt.tight_layout()
    save_plot(plt, title, subfolder=subfolder)
    plt.close()