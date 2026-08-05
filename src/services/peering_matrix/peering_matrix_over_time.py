from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize

DATA_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATTERN = re.compile(
    r"(?:(?P<date>\d{4}[_-]\d{2}[_-]\d{2})_)?(?:peering_matrix_)?proto(?P<proto>\d+)_vlan(?P<vlan>\d+)\.parquet$"
)


def _parse_snapshot_date_token(token: str) -> datetime | None:
    for date_format in ("%Y_%m_%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(token, date_format)
        except ValueError:
            continue
    return None


def _extract_snapshot_date(path: Path) -> datetime | None:
    for part in (path.stem, path.parent.name, *[parent.name for parent in path.parents[1:]]):
        match = re.search(r"(?P<date>\d{4}[_-]\d{2}[_-]\d{2})", part)
        if match:
            parsed = _parse_snapshot_date_token(match.group("date"))
            if parsed is not None:
                return parsed
    return None


def _snapshot_sort_key(snapshot: dict[str, object]) -> tuple[datetime, str]:
    snapshot_date = snapshot.get("snapshot_date")
    if isinstance(snapshot_date, datetime):
        return snapshot_date, str(snapshot["path"])

    path = Path(snapshot["path"])
    return datetime.fromtimestamp(path.stat().st_mtime), str(path)


def _load_snapshot_frame(snapshot: dict[str, object]) -> pd.DataFrame:
    path = Path(snapshot["path"])
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - surfaced to the caller
        raise RuntimeError(f"Failed to load parquet snapshot {path}: {exc}") from exc

    normalized = normalize_snapshot(df, proto=int(snapshot["proto"]), vlan=int(snapshot["vlan"]))
    snapshot_date = snapshot.get("snapshot_date")
    if not isinstance(snapshot_date, datetime):
        snapshot_date = _extract_snapshot_date(path) or datetime.fromtimestamp(path.stat().st_mtime)

    normalized["snapshot_date"] = pd.Timestamp(snapshot_date)
    normalized["snapshot_path"] = str(path)
    return normalized


def resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir) if data_dir is not None else DATA_DIR


def snapshot_path(proto: int | str, vlan: int | str, data_dir: str | Path | None = None) -> Path:
    base_dir = resolve_data_dir(data_dir)
    return base_dir / f"peering_matrix_proto{proto}_vlan{vlan}.parquet"


def list_available_snapshots(data_dir: str | Path | None = None, proto=None, vlan=None) -> list[dict[str, object]]:
    base_dir = resolve_data_dir(data_dir)
    snapshots: list[dict[str, object]] = []
    if not base_dir.exists():
        return snapshots

    for path in sorted(base_dir.rglob("*.parquet")):
        match = SNAPSHOT_PATTERN.search(path.name)
        if not match:
            continue

        proto_from_path = int(match.group("proto"))
        vlan_from_path = int(match.group("vlan"))
        if proto is not None and proto != proto_from_path:
            continue
        if vlan is not None and vlan != vlan_from_path:
            continue

        snapshots.append(
            {
                "proto": proto_from_path,
                "vlan": vlan_from_path,
                "path": path,
                "snapshot_date": _extract_snapshot_date(path),
            }
        )

    snapshots.sort(key=_snapshot_sort_key)
    return snapshots


def normalize_snapshot(df: pd.DataFrame, proto: int | None = None, vlan: int | None = None) -> pd.DataFrame:
    normalized = df.copy()

    for column in ("source_as", "target_as", "status"):
        if column in normalized.columns:
            normalized[column] = normalized[column].astype(str)

    if "proto" not in normalized.columns and proto is not None:
        normalized["proto"] = proto
    if "vlan" not in normalized.columns and vlan is not None:
        normalized["vlan"] = vlan

    if "proto" in normalized.columns:
        normalized["proto"] = normalized["proto"].astype(str)
    if "vlan" in normalized.columns:
        normalized["vlan"] = normalized["vlan"].astype(str)

    return normalized


def load_snapshot(proto: int | str, vlan: int | str, data_dir: str | Path | None = None) -> pd.DataFrame:
    path = snapshot_path(proto, vlan, data_dir=data_dir)
    proto_value = int(proto)
    vlan_value = int(vlan)

    if not path.exists():
        available = list_available_snapshots(data_dir=data_dir, proto=proto_value, vlan=vlan_value)
        available_names = ", ".join(f"proto {item['proto']} vlan {item['vlan']}" for item in available) or "none"
        if not available:
            raise FileNotFoundError(f"Snapshot not found: {path}. Available snapshots: {available_names}")
        return _load_snapshot_frame(available[-1])

    return _load_snapshot_frame({"proto": proto_value, "vlan": vlan_value, "path": path})


def load_all_snapshots(data_dir: str | Path | None = None, proto=None, vlan=None) -> pd.DataFrame:
    snapshots = list_available_snapshots(data_dir=data_dir, proto=proto, vlan=vlan)
    if not snapshots:
        raise FileNotFoundError(f"No parquet snapshots found in {resolve_data_dir(data_dir)}")

    frames = [_load_snapshot_frame(item) for item in snapshots]
    return pd.concat(frames, ignore_index=True)


def unique_asns(df: pd.DataFrame) -> set[str]:
    if df.empty:
        return set()

    sources = set(df["source_as"].dropna().astype(str)) if "source_as" in df.columns else set()
    targets = set(df["target_as"].dropna().astype(str)) if "target_as" in df.columns else set()
    return sources | targets


def peered_edges(df: pd.DataFrame) -> set[tuple[str, str]]:
    if df.empty:
        return set()

    peered = df[df["status"].astype(str) == "peered"]
    if peered.empty:
        return set()

    # Vectorized sorting across rows
    s_as = peered["source_as"].astype(str).to_numpy()
    t_as = peered["target_as"].astype(str).to_numpy()
    
    valid_mask = s_as != t_as
    s_as, t_as = s_as[valid_mask], t_as[valid_mask]

    sorted_pairs = np.sort(np.column_stack((s_as, t_as)), axis=1)
    return set(map(tuple, sorted_pairs))


def all_connections_for_asn(df: pd.DataFrame, asn: int | str) -> pd.DataFrame:
    asn_str = str(asn)
    if df.empty:
        return df.copy()

    s_as = df["source_as"].astype(str)
    t_as = df["target_as"].astype(str)

    is_src = s_as == asn_str
    is_tgt = t_as == asn_str

    subset = df[is_src | is_tgt].copy()
    if subset.empty:
        return subset

    s_as_sub = s_as[subset.index]
    t_as_sub = t_as[subset.index]

    # Vectorized conditional check using np.where
    subset["peer_as"] = np.where(s_as_sub == asn_str, t_as_sub, s_as_sub)
    subset["is_peered"] = subset["status"].astype(str) == "peered"
    return subset.sort_values(["is_peered", "peer_as", "proto", "vlan"], ascending=[False, True, True, True])


def render_peering_recency_grid(
    data_dir: str | Path | None = None,
    proto: int | str = 6,
    vlan: int | str = 1,
    max_days: int = 60,
    annotate: bool = True,
    title: str | None = None,
    save_path: str | Path | None = None,
    figsize: tuple[float, float] | None = None,
):
    """Render an ASN-by-ASN grid colored by how long a peering has been unavailable."""
    history = load_all_snapshots(data_dir=data_dir, proto=int(proto), vlan=int(vlan))
    if history.empty:
        raise FileNotFoundError(f"No peering history found for proto {proto} vlan {vlan} in {resolve_data_dir(data_dir)}")

    history = history.copy()
    history["source_as"] = history["source_as"].astype(str)
    history["target_as"] = history["target_as"].astype(str)
    history["status"] = history["status"].astype(str)
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"], errors="coerce")
    history = history.dropna(subset=["snapshot_date"])
    if history.empty:
        raise ValueError(f"No dated snapshots found for proto {proto} vlan {vlan}")

    def asn_sort_key(value: str) -> tuple[int, int | str]:
        return (0, int(value)) if value.isdigit() else (1, value)

    # Vectorized canonical pair ordering without df.apply
    src_as = history["source_as"].to_numpy()
    tgt_as = history["target_as"].to_numpy()

    # Pre-parse integers for digits to speed up sorting comparisons vectorized
    src_is_digit = np.char.isdigit(src_as)
    tgt_is_digit = np.char.isdigit(tgt_as)

    # Compare sort keys vectorized: (0, int) vs (1, str)
    swap_mask = np.where(
        src_is_digit & tgt_is_digit,
        src_as.astype(np.int64) > tgt_as.astype(np.int64),
        np.where(
            src_is_digit != tgt_is_digit,
            ~src_is_digit,  # Non-digit is greater than digit
            src_as > tgt_as
        )
    )

    history["asn_left"] = np.where(swap_mask, tgt_as, src_as)
    history["asn_right"] = np.where(swap_mask, src_as, tgt_as)

    history = history[history["asn_left"] != history["asn_right"]]
    history["is_peered"] = history["status"].eq("peered")

    peered_history = history[history["is_peered"]].drop_duplicates(subset=["snapshot_date", "asn_left", "asn_right"])
    if peered_history.empty:
        raise ValueError(f"No peered connections found for proto {proto} vlan {vlan}")

    latest_snapshot_date = history["snapshot_date"].max()
    if pd.isna(latest_snapshot_date):
        raise ValueError(f"Unable to determine a latest snapshot date for proto {proto} vlan {vlan}")

    observed_pairs = set(zip(history["asn_left"], history["asn_right"]))
    last_seen = peered_history.groupby(["asn_left", "asn_right"])["snapshot_date"].max()

    asns = sorted(unique_asns(history), key=asn_sort_key)
    asn_map = {asn: idx for idx, asn in enumerate(asns)}

    grid_arr = np.full((len(asns), len(asns)), np.nan, dtype=float)
    annot_arr = np.full((len(asns), len(asns)), "", dtype=object)

    for (asn_left, asn_right), seen_at in last_seen.items():
        if asn_left in asn_map and asn_right in asn_map:
            l_idx, r_idx = asn_map[asn_left], asn_map[asn_right]
            age_days = max((latest_snapshot_date - seen_at).days, 0)
            capped_days = min(age_days, max_days)
            label = str(age_days) if age_days < max_days else f"{max_days}+"

            grid_arr[l_idx, r_idx] = capped_days
            grid_arr[r_idx, l_idx] = capped_days
            annot_arr[l_idx, r_idx] = label
            annot_arr[r_idx, l_idx] = label

    for asn_left, asn_right in observed_pairs:
        if asn_left in asn_map and asn_right in asn_map:
            l_idx, r_idx = asn_map[asn_left], asn_map[asn_right]
            if np.isnan(grid_arr[l_idx, r_idx]):
                grid_arr[l_idx, r_idx] = max_days
                grid_arr[r_idx, l_idx] = max_days
                annot_arr[l_idx, r_idx] = "never"
                annot_arr[r_idx, l_idx] = "never"

    grid = pd.DataFrame(grid_arr, index=asns, columns=asns)
    annotations = pd.DataFrame(annot_arr, index=asns, columns=asns)

    if figsize is None:
        side = max(8.0, min(28.0, len(asns) * 0.35))
        figsize = (side, side)

    fig, ax = plt.subplots(figsize=figsize)
    cmap = LinearSegmentedColormap.from_list("peering_recency", ["#1a9850", "#fee08b", "#d73027"])
    norm = Normalize(vmin=0, vmax=max_days)
    masked_grid = np.ma.masked_invalid(grid_arr)
    im = ax.imshow(masked_grid, cmap=cmap, norm=norm, origin="upper")

    ax.set_xticks(range(len(asns)))
    ax.set_yticks(range(len(asns)))
    ax.set_xticklabels(asns, rotation=90, fontsize=8)
    ax.set_yticklabels(asns, fontsize=8)
    ax.set_xlabel("Target AS")
    ax.set_ylabel("Source AS")
    ax.set_aspect("equal")
    ax.set_xlim(-0.5, len(asns) - 0.5)
    ax.set_ylim(len(asns) - 0.5, -0.5)
    ax.set_title(title or f"Peering recency grid for proto {proto} vlan {vlan}")

    if annotate:
        valid_mask = ~np.isnan(grid_arr)
        np.fill_diagonal(valid_mask, False)
        rows, cols = np.where(valid_mask)

        for r, c in zip(rows, cols):
            cell_value = grid_arr[r, c]
            cell_label = annot_arr[r, c]
            text_color = "white" if cell_value >= max_days * 0.55 else "black"
            ax.text(c, r, cell_label, ha="center", va="center", color=text_color, fontsize=7)

    colorbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label(f"Days since last seen, capped at {max_days}")
    fig.tight_layout()

    if save_path is not None:
        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
		fig.savefig(output_path, bbox_inches="tight")

	return fig, ax, grid

if __name__ == "__main__":
	# Example usage
	render_peering_recency_grid(data_dir="peering_matrix/ix.nap.africa", proto=4, vlan=1, max_days=60, annotate=True, title="Peering Recency Grid", save_path="peering_recency_grid.png")