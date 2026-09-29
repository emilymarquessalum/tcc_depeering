
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from bview_sqlite_parser import (
    compare_hegemony_for_several_dates,
    compare_hegemony_for_two_dates,
    get_first_and_last_date_available_for_asn_data,
    get_interval_dates_for_asn_data,
)
from global_hegemony import analyze_global_hegemony_over_time
from top_hegemony import analyze_top5_vs_others_hegemony_over_time
from vpp_hegemony import compare_vpp_and_non_vpp_hegemony_over_time


def main():
    asn = 15169
    alpha = 0.34
    ip_versions = ["v4", "v6"]
    use_strict_viewpoint_filtering = True
    use_free_viewpoint_filtering = False
    show_as_percentage = True

    # Shared color mapping
    as_color_map = {}

    rrc_target = "rrc03"
    all_rrcs = [
        "rrc00", "rrc01", "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08",
        "rrc09", "rrc10", "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16",
        "rrc17", "rrc18", "rrc19", "rrc20", "rrc21", "rrc22"
    ]

    for ip_version in ip_versions:
        print("=== 1. Running Single RRC Hegemony Over Time ===")
        dates_rrc = get_interval_dates_for_asn_data(
            asn, rrc_target, ip_version, month_interval=6
        )
        compare_hegemony_for_several_dates(
            asn, alpha, rrc_target, ip_version, dates_rrc,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
            show_as_percentage=show_as_percentage,
            as_color_map=as_color_map
        )

        print("\n=== 2. Running Global Hegemony Over Time (All RRCs) ===")
        analyze_global_hegemony_over_time(
            asn=asn,
            alpha=alpha,
            ip_version=ip_version,
            rrc_list=all_rrcs,
            month_interval=6,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            show_as_percentage=show_as_percentage,
            as_color_map=as_color_map
        )

        print("\n=== 3. Running Top 5 vs. Others Hegemony Share ===")
        analyze_top5_vs_others_hegemony_over_time(
            asn=asn,
            alpha=alpha,
            ip_version=ip_version,
            date_list=dates_rrc,
            rrc_used=rrc_target,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
        )

        print("\n=== 4. Running VPP vs. Non-VPP Hegemony Over Time ===")
        compare_vpp_and_non_vpp_hegemony_over_time(
            asn, alpha, rrc_target, ip_version, dates_rrc,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            show_as_percentage=show_as_percentage
        )


if __name__ == "__main__":
    main()