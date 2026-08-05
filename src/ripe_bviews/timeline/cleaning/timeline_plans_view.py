import calendar
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- Data Input ---
plan = [
    ("“how many ASes are peering and depeering in each IXP over time?”", "07-06-2026", "07-31-2026",
     [
         ("Peering Matrix", "07-06-2026", "07-12-2026"),
         ("Confirm real de-peer", "07-13-2026", "07-19-2026"),
         ("depeered ASes show reachability-loss before?", "07-13-2026", "07-19-2026"),
         ("Expand analysis (more IXPs, time range)", "07-19-2026", "07-25-2026"),
         ("Decreasing routes-announced also decreases routes visible for the AS?", "07-19-2026", "07-25-2026"),
     ]
     ),
    ("“Is this reducing route diversity and making the Internet less resilient?”", "08-01-2026", "08-31-2026",
     [
         
         ("Update Hegemony code", "08-01-2026", "08-07-2026"),
         ("Hegemony for mixed viewpoints", "08-01-2026", "08-07-2026"),
         ("How many different ASes were passed in routes", "08-08-2026", "08-15-2026"),
         ("Route Diversity", "08-08-2026", "08-15-2026"),
         ("Route Diversity", "08-16-2026", "08-15-2026"),
     ]
     ),
    ("“Is there an increase in depeering when a content provider or CDN leaves the IXP route server?”", "09-01-2026", "09-30-2026"),
    ("“Is this affecting the performance of traffic delivery?”", "10-01-2026", "10-31-2026"),
    ("“How is this affecting the reachability of the IXP...?”", "11-01-2026", "11-15-2026"),
    ("“When an AS depeers from an IXP, is it doing this from multiple IXPs?”", "11-15-2026", "11-30-2026"),
    ("Extras", "12-01-2026", "02-20-2027")
] 

# Parse dates and truncate long text for the legend
parsed_plan = []
for title, start_str, end_str in plan:
    start_dt = datetime.strptime(start_str, "%m-%d-%Y").date()
    end_dt = datetime.strptime(end_str, "%m-%d-%Y").date()
    short_title = title # title[:60] + "..." if len(title) > 60 else title
    parsed_plan.append((short_title, start_dt, end_dt))

# --- Determine Necessary Months ---
all_dates = [dt for _, start, end in parsed_plan for dt in (start, end)]
min_date, max_date = min(all_dates), max(all_dates)

months_to_render = []
curr_year, curr_month = min_date.year, min_date.month
while (curr_year, curr_month) <= (max_date.year, max_date.month):
    months_to_render.append((curr_year, curr_month))
    if curr_month == 12:
        curr_month = 1
        curr_year += 1
    else:
        curr_month += 1

# --- Layout Configuration ---
num_cols = 4
num_rows = (len(months_to_render) + num_cols - 1) // num_cols

# 1. Lower month_row_padding down now (e.g., 0.05 to 0.1)
month_row_padding = 0.15  

# 2. Adjusted figsize width (13) relative to height to keep calendars square-ish 
# without relying on ax.set_aspect('equal')
fig, axes = plt.subplots(num_rows, num_cols, figsize=(13, 3.8 * num_rows), dpi=120)
axes = axes.flatten()

# Cohesive Palette
palette = ["#CFDDE6", "#1A98FF", "#A8DADC", "#7BCA9F", "#E9C46A", "#F4A261", "#E76F51"]
phase_handles = {}

# --- Draw Calendars ---
for idx, (year, month) in enumerate(months_to_render):
    ax = axes[idx]
    ax.set_title(f"{calendar.month_name[month]} {year}", fontsize=10, fontweight='bold', pad=10, color="#333333")
    
    # 3. REMOVED: ax.set_aspect('equal') 
    ax.axis('off')
    
    days_of_week = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    for d_idx, day_name in enumerate(days_of_week):
        ax.text(d_idx + 0.5, 6.5, day_name, ha='center', va='center', fontsize=8, fontweight='semibold', color='#777777')
        
    month_cal = calendar.monthcalendar(year, month)
    
    for row_idx, week in enumerate(month_cal):
        y_pos = 5.5 - row_idx 
        for col_idx, day in enumerate(week):
            x_pos = col_idx
            if day == 0:
                continue 
                
            day_date = datetime(year, month, day).date()
            ax.text(x_pos + 0.5, y_pos + 0.5, str(day), ha='center', va='center', fontsize=8, color='#222222', zorder=4)
            
            for p_idx, (title, start, end) in enumerate(reversed(parsed_plan)):
                actual_idx = len(parsed_plan) - 1 - p_idx
                if start <= day_date <= end:
                    color = palette[actual_idx % len(palette)]
                    
                    rect = patches.FancyBboxPatch(
                        (x_pos + 0.08, y_pos + 0.08), 0.84, 0.84,
                        boxstyle="round,pad=0.03",
                        linewidth=0,
                        edgecolor="none",
                        facecolor=color,
                        alpha=0.75,
                        zorder=2
                    )
                    ax.add_patch(rect)
                    
                    if title not in phase_handles:
                        phase_handles[title] = patches.Patch(color=color, label=title, alpha=0.8)
                    break 
                    
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 7)

for idx in range(len(months_to_render), len(axes)):
    axes[idx].axis('off')

# 4. Now wspace controls the *true* gap directly.
fig.subplots_adjust(
    top=0.92, 
    bottom=0.32, 
    left=0.05, 
    right=0.95, 
    wspace=month_row_padding,  
    hspace=0.25                 
) 

#ordered_handles = [phase_handles[t[:60] + "..." if len(t) > 60 else t] for t, _, _ in plan if (t[:60] + "..." if len(t) > 60 else t) in phase_handles]
ordered_handles = [phase_handles[t] for t, _, _ in plan if (t) in phase_handles]
fig.legend(
    handles=ordered_handles, 
    loc='lower center', 
    bbox_to_anchor=(0.5, 0.04), 
    ncol=1, 
    fontsize=9,        
    frameon=True,
    facecolor='#F9F9F9',
    edgecolor='#E0E0E0',
    title="Project Phases / Research Questions",
    title_fontproperties={'weight':'bold', 'size': 10} 
)

plt.savefig("calendar_plan.png", bbox_inches='tight', dpi=300)
print("Saved to calendar_plan.png")
plt.show()