import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle, Polygon, FancyArrowPatch
import numpy as np
from scipy.interpolate import make_interp_spline

def plot_cdn_peering_regions(): 
    fig, ax = plt.subplots(figsize=(10, 9))
    
    # Define the thresholds (0-1 scale for each axis)
    low_threshold = 0.33
    mid_threshold = 0.67

    show_intermediary_labels = False
    
    # Define regions with their labels and colors
    regions = [
        # (x_min, x_max, y_min, y_max, label, color)    
        (0, low_threshold, 0, low_threshold, "Hierarchical", "#FF6B6B"),
        (0, low_threshold, low_threshold, mid_threshold, show_intermediary_labels and "Loose Hierarchy" or "---a", "#FFD93D"),
        (0, low_threshold, mid_threshold, 1, "'Anti-Stream' Flattening", "#FFB13D"),
        (low_threshold, mid_threshold, 0, low_threshold, show_intermediary_labels and "Well-Distributed Hierarchy" or "---b", "#FFD93D"),
        (low_threshold, mid_threshold, low_threshold, mid_threshold, "Flattening", "#4D96FF"),
        (low_threshold, mid_threshold, mid_threshold, 1, show_intermediary_labels and "Efficient Flattening" or "---c", "#ECFF3D"),
        (mid_threshold, 1, 0, low_threshold, "Off-Net", "#FF2D2D"),
        (mid_threshold, 1, low_threshold, mid_threshold, 
         "'Stream' Flattening", "#9D84B7"
         ),
        (mid_threshold, 1, mid_threshold, 1, "Mega Flattening" if False else "'Ideal' Flattening", "#6BCB77"),
    ]
    
    # Draw rectangles for each region
    for x_min, x_max, y_min, y_max, label, color in regions:
        rect = Rectangle(
            (x_min, y_min),
            x_max - x_min,
            y_max - y_min,
            linewidth=2,
            edgecolor="black",
            facecolor=color,
            alpha=0.7
        )
        ax.add_patch(rect)
        
        # Add text label in the center of each region
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        
        ax.text(
            x_center,
            y_center,
            label,
            fontsize=11,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.8, edgecolor="none"),
            zorder=10
        )
    
    # Set axis labels and title
    ax.set_xlabel("content-proximity-to-end-user/Demand for Speed", fontsize=14, fontweight="bold")
    ax.set_ylabel("Peering/Demand for Reach", fontsize=14, fontweight="bold")
    ax.set_title("Theoretical Internet Structural Flattening Evolution", fontsize=16, fontweight="bold")
    
    # Set axis limits
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle="--")
     
    arrow = FancyArrowPatch(
        (0.05, 0.05),
        (0.95, 0.95),
        arrowstyle="->,head_width=0.04,head_length=0.04",
        linewidth=3,
        color="purple",
        alpha=0.6,
        zorder=5
    )
    ax.add_patch(arrow)
    
  
    ''' # makes no sense for this graph
    arrow = FancyArrowPatch(
        (0.5, 0.05),
        (0.5, 0.95),
        arrowstyle="->,head_width=0.04,head_length=0.04",
        linewidth=3,
        color="red",
        alpha=0.6,
        zorder=5
    )
    ax.add_patch(arrow)
    '''
  
    
    # Add curved green line for "Timeline"
    # Points: Hierarchical center (0.165, 0.165) -> Flattening center (0.5, 0.5) -> Late Flattening center (0.835, 0.5)
    x_points = np.array([0.165, 0.5, 0.835])
    y_points = np.array([0.165, 0.5, 0.5])
    
    # Create smooth curve using spline
    spl = make_interp_spline(x_points, y_points, k=2)
    x_smooth = np.linspace(x_points[0], x_points[-1], 300)
    y_smooth = spl(x_smooth)
    
    ax.plot(x_smooth, y_smooth, color="green", linewidth=3, alpha=0.7, zorder=4, label="Timeline")
    
    # Add invisible line for legend entry
    ax.plot([0.05, 0.95], [0.05, 0.95], color="purple", linewidth=3, alpha=0.6, zorder=5, label="Flattening")
    
    #ax.plot([0.05, 0.95], [0.05, 0.95], color="red", linewidth=3, alpha=0.6, zorder=5, label="Public Internet Divide")
    
    # Create legend
    ax.legend(loc="upper left", fontsize=11, framealpha=0.95)
    
    # Set aspect ratio to be equal
    ax.set_aspect("equal")
    
    plt.tight_layout()
    return fig, ax


if __name__ == "__main__":
    fig, ax = plot_cdn_peering_regions()
    plt.savefig("cdn_peering_regions.png", dpi=300, bbox_inches="tight")
    #plt.show()
