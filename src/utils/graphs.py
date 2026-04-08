
import os
from matplotlib.offsetbox import AnchoredText
import scienceplots
import matplotlib.pyplot as plt
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from definitions import ROOT_DIR, append_root

plt.style.use(['science', 'no-latex'])

import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*FigureCanvasAgg.*')

# Track graphs rendered in this session
_session_rendered_graphs = []

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
    save_fig_file = f'{folder}{title.replace(" ", "_").lower()}.png'
    fig.savefig(save_fig_file, bbox_inches='tight')
    print(f"Saved plot to: {save_fig_file}")
    
    # Track graph in session
    _session_rendered_graphs.append((save_fig_file, title, subfolder))


starting_folder = append_root("graphs/")
def plot_as_path_length_distribution(as_path_count, title='AS Path Length Distribution'):
    lengths = list(as_path_count.keys())
    counts = list(as_path_count.values())
    
    plt.figure(figsize=(8, 6))
    plt.bar(lengths, counts, color='skyblue')
    plt.xlabel('AS Path Length')
    plt.ylabel('Number of Occurrences')
    plt.title(title)
    plt.xticks(lengths)
    plt.grid(axis='y')

    save_plot(plt, title)
    plt.close()


def plot_list_as_line_plot(data_list, y=None, title='Data Line Plot', xlabel='Index', ylabel='Value', positive_color='green', negative_color='red',subfolder=None, max_labels=None, annotations=None, use_fill=True):
    
     
    assert y is None or len(data_list) == len(y), "Length of data_list and y must be the same if y is provided. Lengths: data_list: {}, y: {}".format(len(data_list), len(y))
    plt.figure(figsize=(12, 6))
    x_indices = list(range(len(data_list)))  # Always use numeric indices for calculations
    x_labels = list(y) if y is not None else x_indices  # Use provided labels for display
    
    marker = "o" if len(data_list) <= 30 else None
     
    # Plot with conditional coloring based on positive/negative values
    if positive_color and negative_color:
        # Plot line
        plt.plot(x_indices, data_list, marker=marker, linestyle='-', color='black', linewidth=2)
        
        # Fill area under the curve with single calls per contiguous region (avoids overlapping transparency/stripes)
        if use_fill:
            # Separate into regions by sign to avoid overlapping fills
            i = 0
            while i < len(data_list):
                # Find contiguous region with same sign
                start_idx = i
                start_val = data_list[i]
                is_positive = start_val >= 0
                
                # Extend region while values have same sign
                while i < len(data_list) and (data_list[i] >= 0) == is_positive:
                    i += 1
                
                end_idx = i
                color = positive_color if is_positive else negative_color
                
                # Fill this entire region in one call
                if end_idx > start_idx:
                    x_region = x_indices[start_idx:end_idx]
                    y_region = data_list[start_idx:end_idx]
                    plt.fill_between(x_region, 0, y_region, alpha=0.3, color=color)
    else:
        plt.plot(x_indices, data_list, marker=marker, linestyle='-', color='orange')
    
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)

    if annotations:
        for at in (annotations):
            
            plt.gca().add_artist(at)
    
    # Handle too many labels
    if max_labels and len(x_labels) > max_labels:
        step = len(x_labels) // max_labels
        tick_positions = x_indices[::step]
        tick_labels = [x_labels[i] if isinstance(x_labels[i], str) else x_labels[i] for i in range(0, len(x_labels), step)]
        plt.xticks(tick_positions, tick_labels, rotation=45)
    else:
        plt.xticks(x_indices, x_labels, rotation=45)
    plt.grid()

    
    save_plot(plt, title, subfolder=subfolder)
    plt.close()

def plot_map_as_bar_plot(data_map, title='Data Bar Plot', xlabel='Key', ylabel='Value', subfolder=None, max_x_value=None, max_labels=None, use_colors=False, use_rotated_labels=True):
    keys = list(data_map.keys())
    keys = sorted(keys)
    values = [data_map[key] for key in keys]
    
    plot_list_as_bar_plot(keys, y=values, title=title, xlabel=xlabel, ylabel=ylabel,
                          colors=get_negative_positive_colors(keys),
                           subfolder=subfolder, max_x_value=max_x_value, max_labels=max_labels, use_colors=use_colors, use_rotated_labels=use_rotated_labels)

def plot_list_as_bar_plot(data_list, y=None, title='Data Bar Plot', xlabel='Index', ylabel='Value', subfolder=None, max_x_value=None, max_labels=None, use_colors=False,
                          colors=None,
                          use_rotated_labels=True):
    plt.figure(figsize=(12, 6))
    assert y is None or len(data_list) == len(y), "Length of data_list and y must be the same if y is provided. Lengths: data_list: {}, y: {}".format(len(data_list), len(y))

    if colors is None:
        colors = get_colors() if use_colors else ['lightgreen'] * len(data_list)
    if y is not None:
        if max_x_value is not None:
            over_x_labels = [label for label in data_list if label > max_x_value]
            over_x_value = 0
            start_index = len(data_list) - len(over_x_labels)
            #print(f"over_x_labels: {over_x_labels}, start_index: {start_index}")
            if over_x_labels:
                for i, label in enumerate(over_x_labels):
                    index = start_index + i
                    #print(f"size of y: {len(y)}, index: {index}")
                    over_x_value += y[index]
                data_list = list(data_list)[:start_index]  
                y = [y[i] for i in range(len(data_list))]
                data_list.append(f'>{max_x_value}')
                y.append(over_x_value)
                 
        plt.bar(range(len(y)), y, color=colors[:len(y)])
        # Handle too many labels
        if max_labels and len(data_list) > max_labels:
            step = len(data_list) // max_labels
            tick_positions = list(range(0, len(data_list), step))
            tick_labels = [data_list[i] for i in tick_positions]
            plt.xticks(tick_positions, tick_labels, rotation=45 if use_rotated_labels else 0)
        else:
            plt.xticks(range(len(data_list)), data_list, rotation=45 if use_rotated_labels else 0)
    else:
        plt.bar(range(len(data_list)), data_list, color=colors[:len(data_list)])
        # Handle too many labels
        if max_labels and len(data_list) > max_labels:
            step = len(data_list) // max_labels
            tick_positions = list(range(0, len(data_list), step))
            plt.xticks(tick_positions)
        else:
            plt.xticks(range(len(data_list)))
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(axis='y') 
 
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

def plot_stacked_line_plot(data_lists, labels, x_labels=None, title='Stacked Line Plot', xlabel='Index', ylabel='Value', colors=None, subfolder=None, annotations=None, max_labels=None):
    
    assert len(data_lists) > 0, "At least one data list is required"
    assert len(data_lists[0]) > 0, "Data lists cannot be empty"
    assert all(len(data_list) == len(data_lists[0]) for data_list in data_lists), "All data lists must have the same length"
    assert len(labels) == len(data_lists), "Number of labels must match number of data lists"
    assert colors is None or len(colors) >= len(data_lists), "If colors are provided, there must be at least as many colors as data lists"
    assert x_labels is None or len(x_labels) == len(data_lists[0]), "If x_labels are provided, their length, which is {}, must match the length of data lists, which is {}".format(len(x_labels), len(data_lists[0]))

    plt.figure(figsize=(12, 6))
    x_indices = range(len(data_lists[0]))
    
    if colors is None:
        colors = get_colors()
        colors = colors[:len(data_lists[0])]  # Use only as many colors as needed
     
    current_stack = [0] * len(data_lists[0])
    
    for i, data_list in enumerate(data_lists):
        stacked_values = [current_stack[j] + data_list[j] for j in range(len(data_list))]
        plt.fill_between(x_indices, current_stack, stacked_values, alpha=0.7, label=labels[i], color=colors[i % len(colors)])
        plt.plot(x_indices, stacked_values, marker='o', color=colors[i % len(colors)], linewidth=2)
        current_stack = stacked_values
    
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid()
    
    if annotations:
        for at in (annotations):
            
            plt.gca().add_artist(at)
    
    # Set x-axis ticks with labels
    if x_labels is not None:
        if max_labels and len(x_labels) > max_labels:
            step = len(x_labels) // max_labels
            tick_positions = list(range(0, len(x_labels), step))
            tick_labels = [x_labels[i] for i in tick_positions]
            plt.xticks(tick_positions, tick_labels, rotation=45)
        else:
            plt.xticks(list(x_indices), x_labels, rotation=45)
     
    save_plot(plt, title, subfolder=subfolder)
    plt.close()


def create_window_with_all_rendered_graphs_this_session():
    """Create a scrollable window with all graphs rendered in this session displayed in a grid."""
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