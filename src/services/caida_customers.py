import bz2
import json
from pathlib import Path
from typing import Optional
import requests

CACHE_DIR = Path("caida_asrank_cache")

# CAIDA public historical datasets (updated monthly on the 1st of each month)
BASE_SERIAL1_URL = "https://publicdata.caida.org/datasets/as-relationships/serial-1"
BASE_SERIAL2_URL = "https://publicdata.caida.org/datasets/as-relationships/serial-2"


def _to_caida_yyyymm01(snapshot_date: str) -> tuple[str, str]:
    """
    Converts 'YYYY-MM-DD' or 'YYYY-MM' to ('YYYYMM01', 'YYYY-MM-01').
    CAIDA publishes AS-relationship and customer-cone snapshots on the 1st of each month.
    """
    parts = snapshot_date.strip().split("-")
    year, month = int(parts[0]), int(parts[1])
    return f"{year:04d}{month:02d}01", f"{year:04d}-{month:02d}-01"


def _download_bz2_lines(url: str) -> list[str]:
    res = requests.get(url, timeout=60)
    res.raise_for_status()
    decompressed = bz2.decompress(res.content).decode("utf-8", errors="replace")
    return decompressed.splitlines()


def _download_rel_lines(yyyymm01: str) -> list[str]:
    rel_url_s2 = f"{BASE_SERIAL2_URL}/{yyyymm01}.as-rel2.txt.bz2"
    rel_url_s1 = f"{BASE_SERIAL1_URL}/{yyyymm01}.as-rel.txt.bz2"
    try:
        return _download_bz2_lines(rel_url_s2)
    except requests.HTTPError:
        return _download_bz2_lines(rel_url_s1)


def load_historical_caida_snapshot(
    snapshot_date: str,
    cache_dir: Path = CACHE_DIR,
    force_refresh: bool = False,
) -> dict[str, dict]:
    """
    Downloads (and caches) CAIDA's actual historical monthly files for `snapshot_date`:
      - YYYYMM01.ppdc-ases.txt.bz2  (Provider/Peer observed customer cone per ASN)
      - YYYYMM01.as-rel2.txt.bz2  (Inferred p2c and p2p links for direct customer count)
    """
    yyyymm01, iso_date = _to_caida_yyyymm01(snapshot_date)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"caida_hist_{yyyymm01}.json"

    if not force_refresh and cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # 1. Fetch Provider/Peer Observed Customer Cones (ppdc-ases)
    ppdc_url = f"{BASE_SERIAL1_URL}/{yyyymm01}.ppdc-ases.txt.bz2"
    ppdc_lines = _download_bz2_lines(ppdc_url)

    cone_sizes: dict[str, int] = {}
    for line in ppdc_lines:
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        if not tokens:
            continue
        asn = tokens[0]
        cone_sizes[asn] = len(tokens)

    # 2. Fetch Inferred AS Relationships
    rel_lines = _download_rel_lines(yyyymm01)

    direct_customers: dict[str, int] = {}
    direct_peers: dict[str, int] = {}
    direct_providers: dict[str, int] = {}

    for line in rel_lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        as1, as2, rel_type = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if rel_type == "-1":
            direct_customers[as1] = direct_customers.get(as1, 0) + 1
            direct_providers[as2] = direct_providers.get(as2, 0) + 1
        elif rel_type == "0":
            direct_peers[as1] = direct_peers.get(as1, 0) + 1
            direct_peers[as2] = direct_peers.get(as2, 0) + 1

    # 3. Combine all observed ASNs and compute historical rank by customer cone size
    all_asns = (
        set(cone_sizes.keys())
        | set(direct_customers.keys())
        | set(direct_peers.keys())
        | set(direct_providers.keys())
    )

    sorted_asns = sorted(
        all_asns,
        key=lambda a: (
            cone_sizes.get(a, 1),
            direct_customers.get(a, 0),
            -int(a) if a.isdigit() else 0,
        ),
        reverse=True,
    )

    snapshot_index: dict[str, dict] = {}
    for rank_idx, asn in enumerate(sorted_asns, start=1):
        total_cone = cone_sizes.get(asn, 1)
        snapshot_index[asn] = {
            "asn": asn,
            "asn_name": None,
            "snapshot_date": iso_date,
            "rank": rank_idx,
            "direct_customers": direct_customers.get(asn, 0),
            "direct_peers": direct_peers.get(asn, 0),
            "direct_providers": direct_providers.get(asn, 0),
            "total_cone_asns": total_cone,
            "downstream_cone_asns": max(0, total_cone - 1),
            "cone_prefixes": None,
            "cone_addresses": None,
        }

    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot_index, f)

    return snapshot_index


def load_historical_customer_lists(
    snapshot_date: str,
    target_asns: list[str],
    cache_dir: Path = CACHE_DIR,
    force_refresh: bool = False,
) -> dict[str, dict[str, list[str]]]:
    """
    Extracts and caches the actual direct and downstream customer ASN lists
    for `target_asns` on `snapshot_date`:
      {
        "29119": {
          "direct_customer_asns": ["...", ...],
          "downstream_cone_asns_list": ["...", ...],
        },
        ...
      }
    """
    target_set = {str(a).strip() for a in target_asns}
    yyyymm01, _ = _to_caida_yyyymm01(snapshot_date)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"caida_customer_lists_{yyyymm01}.json"

    cached: dict[str, dict[str, list[str]]] = {}
    if not force_refresh and cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            cached = json.load(f)
        if target_set.issubset(cached.keys()):
            return {asn: cached[asn] for asn in target_set}

    missing_asns = target_set if force_refresh else (target_set - set(cached.keys()))

    # 1. Full customer cone from ppdc-ases (tokens[0] is provider, tokens[1:] are cone ASNs)
    ppdc_url = f"{BASE_SERIAL1_URL}/{yyyymm01}.ppdc-ases.txt.bz2"
    ppdc_lines = _download_bz2_lines(ppdc_url)

    cone_lists: dict[str, list[str]] = {}
    for line in ppdc_lines:
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        if tokens and tokens[0] in missing_asns:
            cone_lists[tokens[0]] = [t for t in tokens[1:] if t != tokens[0]]

    # 2. Direct customers from as-rel2 / as-rel (rel_type == "-1" -> as1 is provider, as2 is customer)
    rel_lines = _download_rel_lines(yyyymm01)
    direct_lists: dict[str, list[str]] = {asn: [] for asn in missing_asns}

    for line in rel_lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        as1, as2, rel_type = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if rel_type == "-1" and as1 in missing_asns:
            direct_lists[as1].append(as2)

    for asn in missing_asns:
        cached[asn] = {
            "direct_customer_asns": sorted(set(direct_lists.get(asn, []))),
            "downstream_cone_asns_list": sorted(set(cone_lists.get(asn, []))),
        }

    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cached, f)

    return {asn: cached[asn] for asn in target_set}


class ASRankCustomerAnalyzer:
    """
    Loads authentic historical CAIDA ASRank monthly archive snapshots for customer cone analysis.
    """

    def __init__(
        self,
        snapshot_date: Optional[str] = None,
        max_rank_depth: int = 90000,
        force_refresh: bool = False,
    ):
        if not snapshot_date:
            raise ValueError("snapshot_date is required (e.g. '2022-06-01').")
        self.snapshot_date = snapshot_date
        self.asn_index = load_historical_caida_snapshot(
            snapshot_date=snapshot_date,
            force_refresh=force_refresh,
        )

    def get_customer_cones(self, input_asns: list[str]) -> dict[str, Optional[dict]]:
        return {
            str(asn).strip(): self.asn_index.get(str(asn).strip())
            for asn in input_asns
        }

    def get_customer_asn_lists(
        self,
        input_asns: list[str],
        force_refresh: bool = False,
    ) -> dict[str, dict[str, list[str]]]:
        return load_historical_customer_lists(
            snapshot_date=self.snapshot_date,
            target_asns=[str(a).strip() for a in input_asns],
            force_refresh=force_refresh,
        )