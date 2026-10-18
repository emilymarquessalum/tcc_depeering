import sys

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_all_files, get_data
from src.caidapeeringdb.vpps.main import build_vpp_asn_map

def extract_as_metrics_from_snapshot(snapshot, target_asns):
    """
    Extrai métricas agregadas por AS a partir de um snapshot do PeeringDB.
    Retorna um dicionário: { asn: {'num_ixps': int, 'total_speed': float} }
    """
    as_metrics = {asn: {"num_ixps": 0, "total_speed": 0.0} for asn in target_asns}
    netixlan_entries = snapshot.get("netixlan", {}).get("data", [])

    for conn in netixlan_entries:
        raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
        if raw_asn is None:
            continue

        try:
            conn_asn = int(raw_asn)
        except (ValueError, TypeError):
            continue

        if conn_asn in target_asns:
            as_metrics[conn_asn]["num_ixps"] += 1

            speed = conn.get("speed")
            if speed is not None:
                try:
                    speed_val = float(speed)
                    if speed_val > 0:
                        as_metrics[conn_asn]["total_speed"] += speed_val
                except (ValueError, TypeError):
                    pass

    return as_metrics


def plot_vpp_growth_cdf(
    all_files,
    all_snapshots,
    vpp_asn_map,
    start_date_str=None,
    end_date_str=None,
    metric="total_speed",  # Opções: 'total_speed' ou 'num_ixps'
    filter_zero_start=True,
    output_dir="plots/vpps"
):
    """
    Gera a CDF do crescimento percentual (%) de uma métrica para os ASes entre duas datas.
    """
    dates = [file.split("dump_")[-1].split(".")[0].replace("_", "-") for file in all_files]

    # Identificação das datas inicial e final
    if start_date_str and start_date_str in dates:
        start_idx = dates.index(start_date_str)
    else:
        start_idx = 0

    if end_date_str and end_date_str in dates:
        end_idx = dates.index(end_date_str)
    else:
        end_idx = -1

    start_date = dates[start_idx]
    end_date = dates[end_idx]

    start_snapshot = all_snapshots[start_idx]
    end_snapshot = all_snapshots[end_idx]

    target_asns = set(vpp_asn_map.keys())

    start_metrics = extract_as_metrics_from_snapshot(start_snapshot, target_asns)
    end_metrics = extract_as_metrics_from_snapshot(end_snapshot, target_asns)

    growth_percentages = []

    for asn in target_asns:
        v_start = start_metrics[asn][metric]
        v_end = end_metrics[asn][metric]

        if v_start == 0:
            if filter_zero_start:
                # Ignora ASes com valor inicial 0 para não ter divisão por zero / crescimento infinito
                continue
            else:
                growth_pct = 100.0 if v_end > 0 else 0.0
        else:
            # Cálculo do crescimento percentual
            growth_pct = ((v_end - v_start) / v_start) * 100.0

        growth_percentages.append(growth_pct)

    if not growth_percentages:
        print("Nenhum AS válido encontrado para os parâmetros selecionados.")
        return

    # Ordena os valores de crescimento percentual
    sorted_growth = np.sort(growth_percentages)
    n = len(sorted_growth)

    # CDF acumulada de 0 a 100%
    cdf_y = np.arange(1, n + 1) / n * 100.0

    # Formatação das legendas e títulos
    metric_labels = {
        "total_speed": "Velocidade Total de Portas",
        "num_ixps": "Quantidade de IXPs Conectados"
    }
    label = metric_labels.get(metric, metric)

    plt.figure(figsize=(10, 6))
    #plt.xlim(-100, 2000)
    # Plot em degraus (step plot) comum para CDFs empíricas
    plt.step(sorted_growth, cdf_y, where="post", color="#1f77b4", linewidth=2, label="CDF de ASes")

    plt.axvline(0, color="red", linestyle="--", alpha=0.7, label="Sem Crescimento (0%)")
    plt.grid(True, linestyle="--", alpha=0.6)

    plt.title(f"CDF do Crescimento Percentual de ASes ({start_date} até {end_date})\nMétrica: {label}", fontsize=13, pad=15)
    plt.xlabel("Crescimento Percentual no Período (%)", fontsize=11)
    plt.ylabel("% Acumulado de ASes", fontsize=11)
    plt.ylim(0, 105)
    plt.legend(fontsize=10)
    plt.tight_layout()

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path / f"cdf_growth_{metric}_{start_date}_to_{end_date}.png", dpi=300)
    plt.show()

    print(f"--- Resumo de Crescimento ({label}) ---")
    print(f"Total de ASes analisados: {n}")
    print(f"Mediana do crescimento: {np.median(sorted_growth):.2f}%")
    print(f"Média do crescimento: {np.mean(sorted_growth):.2f}%")
    print(f"ASes que não cresceram (<= 0%): {np.sum(sorted_growth <= 0) / n * 100:.1f}%")


if __name__ == "__main__":
    all_files = get_all_files() 
    all_snapshots = get_all_data(all_files)
    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)

    # CDF para Capacidade Total de Portas
    plot_vpp_growth_cdf(
        all_files,
        all_snapshots,
        vpp_asn_map,
        metric="total_speed",
        filter_zero_start=True
    )

    # CDF para Número de IXPs conectados
    plot_vpp_growth_cdf(
        all_files,
        all_snapshots,
        vpp_asn_map,
        metric="num_ixps",
        filter_zero_start=True
    )