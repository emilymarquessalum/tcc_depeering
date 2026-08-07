from __future__ import annotations

from pathlib import Path
import argparse

import pandas as pd

from peering_matrix_over_time import all_connections_for_asn, load_all_snapshots, load_snapshot, resolve_data_dir


def search_asn(asn: int | str, proto: int | None = None, vlan: int | None = None, data_dir: str | Path | None = None) -> pd.DataFrame:
	if proto is None or vlan is None:
		matrix = load_all_snapshots(data_dir=data_dir)
	else:
		matrix = load_snapshot(proto, vlan, data_dir=data_dir)

	return all_connections_for_asn(matrix, asn)


def print_search_results(results: pd.DataFrame, asn: int | str) -> None:
	if results.empty:
		print(f"No connections found for AS {asn}.")
		return

	summary = (
		results.groupby("peer_as", as_index=False)
		.agg(
			peered_rows=("is_peered", "sum"),
			total_rows=("peer_as", "size"),
			statuses=("status", lambda values: ", ".join(sorted(set(map(str, values)))))
		)
		.sort_values(["peered_rows", "peer_as"], ascending=[False, True])
	)

	print(f"Connections for AS {asn}:")
	print(summary.to_string(index=False))


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Search the saved matrices for all connections of one AS.")
	parser.add_argument("asn", help="AS number to look up.")
	parser.add_argument("--proto", type=int, help="Protocol to load, for example 4 or 6.")
	parser.add_argument("--vlan", type=int, help="VLAN to load, for example 1 or 2.")
	parser.add_argument("--data-dir", type=Path, default=resolve_data_dir(), help="Directory containing parquet snapshots.")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	results = search_asn(args.asn, proto=args.proto, vlan=args.vlan, data_dir=args.data_dir)
	print_search_results(results, args.asn)


if __name__ == "__main__":
	main()
