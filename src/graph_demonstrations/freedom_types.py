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
    
    # Define regions with their labels and colors
    regions = [
         

        (0, low_threshold, 0, low_threshold, "Great Firewall of -", "#CB866B"),

        (0, low_threshold, low_threshold, mid_threshold,  "Splinternets", "#B784A0"),
        (0, low_threshold, mid_threshold, 1, "Off-Nets", "#9D84B7"),
        (low_threshold, mid_threshold, 0, low_threshold,  "Splinternets", "#B784A0"),
        (low_threshold, mid_threshold, low_threshold, mid_threshold,  "WWW", "#6BCB77"),
        (low_threshold, mid_threshold, mid_threshold, 1,   "WWW", "#6BCB77"),
        (mid_threshold, 1, 0, low_threshold,  "Splinternets", "#B784A0"),
        (mid_threshold, 1, low_threshold, mid_threshold, 
          "WWW", "#6BCB77"
         ),
        (mid_threshold, 1, mid_threshold, 1, "WWW", "#6BCB77"),
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
    ax.set_xlabel("Freedom", fontsize=14, fontweight="bold")
    ax.set_ylabel("Globality", fontsize=14, fontweight="bold")
    ax.set_title("Internet Types of 'Freedom' (wip)", fontsize=16, fontweight="bold")
    
    # Set axis limits
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle="--")
      
    
   
    # Create legend
    ax.legend(loc="upper left", fontsize=11, framealpha=0.95)
    
    # Set aspect ratio to be equal
    ax.set_aspect("equal")
    
    plt.tight_layout()
    return fig, ax


if __name__ == "__main__":
    fig, ax = plot_cdn_peering_regions()
    plt.savefig("freedom_types.png", dpi=300, bbox_inches="tight")
    #plt.show()
