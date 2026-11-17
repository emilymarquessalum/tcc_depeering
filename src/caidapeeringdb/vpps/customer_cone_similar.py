import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from customer_cone import (
    analyze_vpp_customer_cones_over_dates,
    compute_accumulated_cones_over_time,
    compute_top_vpps_over_time,
    export_vpp_cones,
    plot_vpp_cone_analyses,
    plot_vpp_cone_change_distribution,
)


def load_similar_asn_map(json_path: str = "vpp_asn_similar_asrank.json") -> dict[str, str]:
    """
    Loads `vpp_asn_similar_asrank.json` and returns {closest_asn_str: closest_asn_name}.
    """
    with Path(json_path).open("r", encoding="utf-8") as f:
        raw_data = json.load(f)

    similar_map: dict[str, str] = {}
    for entry in raw_data.values():
        if not isinstance(entry, dict) or entry.get("closest_asn") is None:
            continue

        try:
            asn_int = int(str(entry["closest_asn"]).upper().replace("AS", "").strip())
            asn_str = str(asn_int)
        except (ValueError, TypeError):
            continue

        if asn_str not in similar_map:
            raw_name = (entry.get("closest_asn_name") or "").split("\n")[0].strip()
            similar_map[asn_str] = raw_name if raw_name else f"AS{asn_int}"

    return similar_map


if __name__ == "__main__":
    target_dates = [
        "2022-01-01",
        "2022-06-01",
        "2023-01-01",
        "2023-06-01",
        "2024-01-01",
        "2024-06-01",
        "2025-01-01",
        "2025-06-01",
        "2026-01-01",
    ]

    similar_asn_map = load_similar_asn_map("vpp_asn_similar_asrank.json")

    results = analyze_vpp_customer_cones_over_dates(
        dates=target_dates,
        asn_map=similar_asn_map,
    )

    accumulated_cones = compute_accumulated_cones_over_time(results, target_dates)

    top_n = 5
    top_similar = compute_top_vpps_over_time(
        results,
        target_dates,
        top_n=top_n,
        sort_metric="downstream_cone_asns",
    )

    top_n_asns = {
        entry["asn"]
        for entries in top_similar.values()
        for entry in entries
    }

    accumulated_without_top = compute_accumulated_cones_over_time(
        results,
        target_dates,
        exclude_asns=top_n_asns,
    )

    export_vpp_cones(
        results,
        target_dates,
        output_dir="output/similar_ases",
        accumulated=accumulated_cones,
        accumulated_without_top=accumulated_without_top,
        top_vpps=top_similar,
        top_n=top_n,
    )

    plot_vpp_cone_analyses(
        vpp_timeline=results,
        accumulated_cones=accumulated_cones,
        top_vpps=top_similar,
        dates=target_dates,
        metric="downstream_cone_asns",
        subfolder="similar_ases",
        top_n=top_n,
        accumulated_without_top=accumulated_without_top,
    )

    plot_vpp_cone_change_distribution(
        vpp_timeline=results,
        start_date=target_dates[0],
        end_date=target_dates[-1],
        metric="downstream_cone_asns",
        subfolder="similar_ases",
    )