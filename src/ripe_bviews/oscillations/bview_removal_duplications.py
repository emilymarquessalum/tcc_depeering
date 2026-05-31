 
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.ripe_bviews.timeline.bview_timeline import load_bview_data


start_date = datetime(2025, 10, 20)
end_date = datetime(2026, 1, 1)
asn_and_prefix = ("26162", "187.16.216.253")
rrc = "rrc15"

all_stats, labels = load_bview_data(start_date, end_date, asn_and_prefix, rrc, day_delta=timedelta(days=3))



# Metric: Count ASes that left and came back multiple times (oscillating ASes)
if all_stats:
	all_asns = set()
	for stat in all_stats:
		all_asns.update(stat.unique_members)

	oscillating_ases = set()
	oscillation_counts = {}
	for asn in all_asns:
		presence = [asn in stat.unique_members for stat in all_stats]
		oscillations = 0
		was_present = presence[0]
		for i in range(1, len(presence)):
			if not was_present and presence[i]:  # False -> True transition (came back)
				oscillations += 1
			was_present = presence[i]
		if oscillations > 0:
			oscillating_ases.add(asn)
			oscillation_counts[asn] = oscillations

	print(f"Number of ASes that left and came back at least once: {len(oscillating_ases)}")
	print(f"Total oscillation events (sum of all ASes): {sum(oscillation_counts.values())}")
	if oscillation_counts:
		avg_oscillations = sum(oscillation_counts.values()) / len(oscillation_counts)
		print(f"Average oscillations per oscillating AS: {avg_oscillations:.2f}")
	else:
		print("No oscillating ASes found.")
else:
	print("No stats loaded.")
