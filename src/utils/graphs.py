
import os
import scienceplots
import matplotlib.pyplot as plt

from definitions import ROOT_DIR, append_root

plt.style.use(['science', 'no-latex'])

import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*FigureCanvasAgg.*')

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
    #print(f"Saved plot to: {save_fig_file}") 


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
    plt.show()


def plot_list_as_line_plot(data_list, y=None, title='Data Line Plot', xlabel='Index', ylabel='Value', positive_color='green', negative_color='red',subfolder=None, max_labels=None):
    plt.figure(figsize=(12, 6))
    x_indices = list(range(len(data_list)))  # Always use numeric indices for calculations
    x_labels = list(y) if y is not None else x_indices  # Use provided labels for display
    
    # Plot with conditional coloring based on positive/negative values
    if positive_color and negative_color:
        for i in range(len(data_list)):
            # Determine color based on current value
            color = positive_color if data_list[i] >= 0 else negative_color
            # Fill from 0 to the value
            if i == 0:
                plt.fill_between([x_indices[i], x_indices[i]], 0, data_list[i], alpha=0.3, color=color)
            else:
                # Fill between previous and current point
                # If segment crosses zero, split it
                prev_val = data_list[i-1]
                curr_val = data_list[i]
                
                if (prev_val >= 0 and curr_val >= 0) or (prev_val < 0 and curr_val < 0):
                    # Both same sign, use one color
                    color = positive_color if curr_val >= 0 else negative_color
                    plt.fill_between([x_indices[i-1], x_indices[i]], 0, [prev_val, curr_val], alpha=0.3, color=color)
                else:
                    # Segment crosses zero, split and use both colors
                    # Calculate intersection point with zero line
                    if prev_val != curr_val:
                        t = abs(prev_val) / (abs(prev_val) + abs(curr_val))  # parameter along segment
                        x_cross = x_indices[i-1] + t * (x_indices[i] - x_indices[i-1])
                        
                        # First half (from prev to zero crossing)
                        plt.fill_between([x_indices[i-1], x_cross], 0, [prev_val, 0], alpha=0.3, 
                                       color=positive_color if prev_val >= 0 else negative_color)
                        # Second half (from zero crossing to current)
                        plt.fill_between([x_cross, x_indices[i]], 0, [0, curr_val], alpha=0.3,
                                       color=positive_color if curr_val >= 0 else negative_color)
            
            # Plot line segment
            if i < len(data_list) - 1:
                plt.plot([x_indices[i], x_indices[i+1]], [data_list[i], data_list[i+1]], 
                        marker='o', linestyle='-', color='black', linewidth=2)
            else:
                plt.plot([x_indices[i]], [data_list[i]], marker='o', color='black', markersize=8)
    else:
        plt.plot(x_indices, data_list, marker='o', linestyle='-', color='orange')
    
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
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
    plt.show()

def plot_list_as_bar_plot(data_list, y=None, title='Data Bar Plot', xlabel='Index', ylabel='Value', subfolder=None, max_x_value=None, max_labels=None):
    plt.figure(figsize=(12, 6))
    
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
                 
        plt.bar(range(len(y)), y, color='lightgreen')
        # Handle too many labels
        if max_labels and len(data_list) > max_labels:
            step = len(data_list) // max_labels
            tick_positions = list(range(0, len(data_list), step))
            tick_labels = [data_list[i] for i in tick_positions]
            plt.xticks(tick_positions, tick_labels, rotation=45)
        else:
            plt.xticks(range(len(data_list)), data_list, rotation=45)
    else:
        plt.bar(range(len(data_list)), data_list, color='lightgreen')
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
    plt.show()

def plot_stacked_line_plot(data_lists, labels, x_labels=None, title='Stacked Line Plot', xlabel='Index', ylabel='Value', colors=None, subfolder=None, max_labels=None):
    plt.figure(figsize=(12, 6))
    x_indices = range(len(data_lists[0]))
    
    if colors is None:
        colors = ['orange', 'lightblue', 'lightgreen', 'red', 'purple']
     
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
    plt.show()