import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

progresses = [
    ("31/03", ["WQ1"]),
    ("08/04", ["WQ2"]),
    ("17/04", ["WQ1", "WQ2"]),
    ("22/04", ["WQ2"]),
    ("28/04", ["WQ3"]),
    ("05/05", ["WQ3", "WQ5", "WQ6"]),
    ("12/05", ["WQ3", "WQ4", "WQ5"]),
    ("18/05", ["WQ3", "WQ4"]),
    ("26/05", ["WQ3", "WQ5"]),
    ("02/06", ["WQ1"]),
    ("09/06", ["NAPAfrica-Analysis"]),
    ("16/06", ["WQ1", "WQ6"]),
    ("23/06", ["WQ6"]),
]

# 1. Collect unique labels for the color palette
all_labels = set()
for _, labels in progresses:
    all_labels.update(labels)
sorted_labels = sorted(list(all_labels))

cmap = plt.get_cmap("tab10")
label_colors = {label: cmap(i % 10) for i, label in enumerate(sorted_labels)}

# 2. ALGORITHM: Align labels with the previous date's positions
aligned_progresses = []
prev_order = []

for date, labels in progresses:
    common = [lbl for lbl in prev_order if lbl in labels]
    new_labels = [lbl for lbl in labels if lbl not in prev_order]
    current_order = common + new_labels
    aligned_progresses.append((date, current_order))
    prev_order = current_order

# 3. Setting up the Plot (Generous 12x6 inches size)
fig, ax = plt.subplots(figsize=(12, 6))

box_ymin = 0.2
box_height = 0.6

for i, (date, labels) in enumerate(aligned_progresses):
    num_labels = len(labels)

    for j, label in enumerate(labels):
        ymin = box_ymin + (j / num_labels) * box_height
        ymax = box_ymin + ((j + 1) / num_labels) * box_height

        rect_stripe = mpatches.Rectangle(
            (i, ymin),
            1,
            ymax - ymin,
            color=label_colors[label],
            ec="none",
        )
        ax.add_patch(rect_stripe)

    rect_border = mpatches.Rectangle(
        (i, box_ymin),
        1,
        box_height,
        linewidth=1.5,
        edgecolor="black",
        facecolor="none",
    )
    ax.add_patch(rect_border)

# 4. Formatting Axes and Labels
ax.set_xlim(-0.5, len(progresses) + 0.5)
ax.set_ylim(0, 1)

# Set X-axis ticks to show the dates
ax.set_xticks([i + 0.5 for i in range(len(progresses))])
# Subtle padding so labels sit cleanly just below the squares
ax.tick_params(axis='x', which='major', pad=8)
ax.set_xticklabels(
    [date for date, _ in progresses], fontsize=6, fontweight="bold"
)

# Clean up Y-axis
ax.get_yaxis().set_visible(False)

# Remove outer borders
for spine in ["top", "right", "left", "bottom"]:
    ax.spines[spine].set_visible(False)

label_counts = {}

all_labels = []
for _, labels in aligned_progresses:
    all_labels.extend(labels)

for label in all_labels:
    if not label in label_counts:
        label_counts[label] = 0
    label_counts[label] += 1

# 5. Add Legend
legend_patches = [
    mpatches.Patch(color=color, label=label + f"({label_counts[label]})")
    for label, color in label_colors.items()
]

# Positioned slightly below the X-axis labels without running off-screen
ax.legend(
    handles=legend_patches,
    loc="upper center",
    bbox_to_anchor=(0.5, -0.15),
    ncol=4,  
    frameon=False,
    fontsize=9
)

plt.title("Progress Timeline by Date", fontsize=12, pad=15, fontweight="bold")

# Hard-coded canvas boundaries: 
# leaving 15% empty space at the top (for title) and 30% at the bottom (for X-axis & legend)
plt.subplots_adjust(top=0.85, bottom=0.30, left=0.05, right=0.95)

plt.show()