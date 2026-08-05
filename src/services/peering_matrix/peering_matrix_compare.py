from __future__ import annotations

from pathlib import Path
import argparse

import pandas as pd

from peering_matrix_over_time import load_snapshot, peered_edges, resolve_data_dir, unique_asns


def compare_configurations(
	proto_a: int,
	vlan_a: int,
	proto_b: int,
	vlan_b: int,
	data_dir: str | Path | None = None,
) -> dict[str, object]:
	matrix_a = load_snapshot(proto_a, vlan_a, data_dir=data_dir)
	matrix_b = load_snapshot(proto_b, vlan_b, data_dir=data_dir)

	asns_a = unique_asns(matrix_a)
	asns_b = unique_asns(matrix_b)
	common_asns = asns_a & asns_b

	edges_a = {edge for edge in peered_edges(matrix_a) if edge[0] in common_asns and edge[1] in common_asns}
	edges_b = {edge for edge in peered_edges(matrix_b) if edge[0] in common_asns and edge[1] in common_asns}

	only_a = edges_a - edges_b
	only_b = edges_b - edges_a
	shared_edges = edges_a & edges_b

	return {
		"config_a": {"proto": proto_a, "vlan": vlan_a, "asns": asns_a, "edges": edges_a},
		"config_b": {"proto": proto_b, "vlan": vlan_b, "asns": asns_b, "edges": edges_b},
		"common_asns": common_asns,
		"common_asn_count": len(common_asns),
		"edges_a_count": len(edges_a),
		"edges_b_count": len(edges_b),
		"shared_edge_count": len(shared_edges),
		"different_edge_count": len(only_a) + len(only_b),
		"only_in_a": only_a,
		"only_in_b": only_b,
		"shared_edges": shared_edges,
	}


def print_comparison_report(report: dict[str, object]) -> None:
	config_a = report["config_a"]
	config_b = report["config_b"]

	print(
		f"Comparing proto {config_a['proto']} vlan {config_a['vlan']} vs proto {config_b['proto']} vlan {config_b['vlan']}"
	)
	print(f"Common ASNs: {report['common_asn_count']}")
	print(f"Connections in common: {report['shared_edge_count']}")
	print(f"Different connections: {report['different_edge_count']}")
	print(f"Only in first config: {len(report['only_in_a'])}")
	print(f"Only in second config: {len(report['only_in_b'])}")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Compare two saved peering matrix snapshots.")
	parser.add_argument("proto_a", type=int, nargs="?", default=4, help="Protocol for the first snapshot.")
	parser.add_argument("vlan_a", type=int, nargs="?", default=1, help="VLAN for the first snapshot.")
	parser.add_argument("proto_b", type=int, nargs="?", default=6, help="Protocol for the second snapshot.")
	parser.add_argument("vlan_b", type=int, nargs="?", default=2, help="VLAN for the second snapshot.")
	parser.add_argument("--data-dir", type=Path, default=resolve_data_dir(), help="Directory containing parquet snapshots.")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	report = compare_configurations(args.proto_a, args.vlan_a, args.proto_b, args.vlan_b, data_dir=args.data_dir)
	print_comparison_report(report)


if __name__ == "__main__":
	main()
