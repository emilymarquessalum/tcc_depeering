from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse

import pandas as pd

from peering_matrix_over_time import load_all_snapshots, load_snapshot, peered_edges, resolve_data_dir


def rank_ases(proto: int | None = None, vlan: int | None = None, data_dir: str | Path | None = None) -> pd.DataFrame:
	if proto is None or vlan is None:
		matrix = load_all_snapshots(data_dir=data_dir)
	else:
		matrix = load_snapshot(proto, vlan, data_dir=data_dir)

	edge_counts: Counter[str] = Counter()
	for source_as, target_as in peered_edges(matrix):
		edge_counts[source_as] += 1
		edge_counts[target_as] += 1

	ranking = pd.DataFrame(
		sorted(edge_counts.items(), 
		 key=lambda item: (-item[1], int(item[0]) if item[0].isdigit() else item[0]),
		 reverse=True),
		columns=["asn", "peered_connections"],
	)
	return ranking


def print_ranking(ranking: pd.DataFrame, top_n: int = 20) -> None:
	if ranking.empty:
		print("No ranked ASNs found.")
		return

	print(ranking.head(top_n).to_string(index=False))


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Rank ASNs by unique peered connections in the saved matrices.")
	parser.add_argument("--proto", type=int, help="Protocol to load, for example 4 or 6.")
	parser.add_argument("--vlan", type=int, help="VLAN to load, for example 1 or 2.")
	parser.add_argument("--top", type=int, default=20, help="Number of rows to display.")
	parser.add_argument("--data-dir", type=Path, default=resolve_data_dir(), help="Directory containing parquet snapshots.")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	ranking = rank_ases(proto=args.proto, vlan=args.vlan, data_dir=args.data_dir)
	print_ranking(ranking, top_n=args.top)


if __name__ == "__main__":
	main()
