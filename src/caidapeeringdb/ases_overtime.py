from src.caidapeeringdb.caidapeeringdb_load import get_asn_from_net
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.utils.graphs import clean_title_name, save_plot

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


def plot_ases_heatmap_over_time(
	all_data,
	dates,
	ixp_ids,
	asn_to_analyze,
	ixp_names=None,
	mode="binary",  # "binary" (present/absent) or "prefix_count"
	title_info="IXPs",
	max_y_ticks=40,
):
	"""
	Plot a heatmap showing presence of an ASN at many IXPs over time.

	- `mode=="binary"`: each cell is 1 if the ASN is present at that IXP snapshot (green), 0 otherwise (red).
	- `mode=="prefix_count"`: each cell contains the number of distinct ipaddr4/ipaddr6 seen at that IXP snapshot (continuous colormap).

	Args:
		all_data: list of snapshot dicts (same structure used elsewhere in this repo).
		dates: list of date labels (strings) aligned with `all_data`.
		ixp_ids: list/tuple/set of IXP ids to include (ints or strings).
		asn_to_analyze: integer ASN to check for presence.
		ixp_names: optional mapping or list for nicer y-axis labels.
		mode: "binary" or "prefix_count".
		title_info: string to include in the plot title.
		max_y_ticks: maximum number of Y ticks to draw (to avoid overcrowding).
	"""
	if ixp_ids is None or len(ixp_ids) == 0:
		raise ValueError("ixp_ids cannot be None or empty")

	if not isinstance(ixp_ids, (list, tuple, set)):
		ixp_ids = [ixp_ids]

	target_ixp_ids = [int(x) for x in ixp_ids]
	snapshot_count = min(len(all_data), len(dates))
	dates = dates[:snapshot_count]
	all_data = all_data[:snapshot_count]

	# Build name map
	ixp_name_map = {}
	if isinstance(ixp_names, dict):
		for k, v in ixp_names.items():
			ixp_name_map[int(k)] = v
	elif isinstance(ixp_names, (list, tuple)):
		for idx, ixp_id in enumerate(target_ixp_ids):
			if idx < len(ixp_names):
				ixp_name_map[int(ixp_id)] = ixp_names[idx]
	elif isinstance(ixp_names, str) and len(target_ixp_ids) == 1:
		ixp_name_map[target_ixp_ids[0]] = ixp_names

	# Prepare matrix: rows = IXPs, cols = snapshots
	matrix = np.zeros((len(target_ixp_ids), len(dates)), dtype=float)

	# For prefix counting mode we collect unique ipaddrs per cell
	if mode == "prefix_count":
		cell_sets = [ [set() for _ in dates] for _ in target_ixp_ids ]

	ixp_index_map = {ixp_id: i for i, ixp_id in enumerate(target_ixp_ids)}

	for col_idx, snapshot in enumerate(all_data):
		for conn in snapshot.get("netixlan", {}).get("data", []):
			ix_id = conn.get("ix_id")
			if ix_id is None:
				continue
			try:
				ix_id = int(ix_id)
			except (TypeError, ValueError):
				continue
			if ix_id not in ixp_index_map:
				continue

			row_idx = ixp_index_map[ix_id]

			# presence test is based on ASN fields
			asn = get_asn_from_net(conn)
			local_asn = conn.get("local_asn")

			if mode == "binary":
				if asn == asn_to_analyze or local_asn == asn_to_analyze:
					matrix[row_idx, col_idx] = 1.0

			elif mode == "prefix_count":
				# use ipaddr4/ipaddr6 as a proxy for distinct prefixes seen
				ip4 = conn.get("ipaddr4")
				ip6 = conn.get("ipaddr6")
				if ip4:
					cell_sets[row_idx][col_idx].add(ip4)
				if ip6:
					cell_sets[row_idx][col_idx].add(ip6)
				# also count presence of the ASN (optional) to avoid empty cells
				if asn == asn_to_analyze or local_asn == asn_to_analyze:
					# mark with a placeholder to indicate presence
					cell_sets[row_idx][col_idx].add(f"asn:{asn_to_analyze}")

	if mode == "prefix_count":
		for i in range(len(target_ixp_ids)):
			for j in range(len(dates)):
				matrix[i, j] = len(cell_sets[i][j])

	# Plotting
	fig, ax = plt.subplots(figsize=(max(8, len(dates)*0.5), max(6, len(target_ixp_ids)*0.15)))

	if mode == "binary":
		cmap = ListedColormap(["#d9534f", "#5cb85c"])  # red, green
		im = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=1)
		cbar = fig.colorbar(im, ax=ax, ticks=[0,1])
		cbar.ax.set_yticklabels(["Absent", "Present"])  # type: ignore
	else:
		im = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="viridis")
		cbar = fig.colorbar(im, ax=ax)
		cbar.set_label("Distinct ipaddr4/ipaddr6 count")

	# Y ticks: IXP labels
	y_labels = [ixp_name_map.get(ixp_id, f"IXP {ixp_id}") for ixp_id in target_ixp_ids]
	if len(y_labels) <= max_y_ticks:
		ax.set_yticks(range(len(y_labels)))
		ax.set_yticklabels(y_labels)
	else:
		# show a subset of labels to avoid crowding
		step = max(1, len(y_labels) // max_y_ticks)
		tick_positions = list(range(0, len(y_labels), step))
		ax.set_yticks(tick_positions)
		ax.set_yticklabels([y_labels[i] for i in tick_positions])

	# X ticks: dates, rotate if needed
	if len(dates) > 12:
		stepx = max(1, len(dates)//12)
		xticks = list(range(0, len(dates), stepx))
		ax.set_xticks(xticks)
		ax.set_xticklabels([dates[i] for i in xticks], rotation=45)
	else:
		ax.set_xticks(range(len(dates)))
		ax.set_xticklabels(dates, rotation=45)

	ax.set_xlabel("Date")
	ax.set_ylabel("IXP")

	title = f"ASN {asn_to_analyze} Presence at {title_info} Over Time ({mode})"
	plt.title(title)
	ax.grid(False)

	save_plot(plt, clean_title_name(f"ases_heatmap_{asn_to_analyze}_{mode}"), subfolder=PEERINGDB_SUBFOLDER_PREFIX + "ases_overtime")
	plt.close()

