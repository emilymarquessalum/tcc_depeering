import math
from pathlib import Path
import sys

from src.caidapeeringdb.caidapeeringdb_load import get_asinfo_from_asn
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_asn_data_timeline_from_configs
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.asn import get_formatted_asn_name

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))  

import numpy as np
from collections import defaultdict

from src.ripe_bviews.timeline.bview_vars import get_ip_version, get_subfolder
from src.utils.graphs import create_colors_for_groups, plot_list_as_bar_plot, plot_list_as_line_plot

# Mock ou assinatura para a função assumida internamente
def get_collector_data_for_asn(asn: int) -> list[BGPDumpSnapshotStats]:
    """
    Função interna assumida que busca dados de coletores específicos 
    filtrados/relacionados a um determinado ASN.
    """
    # Exemplo de retorno conceitual. Substitua pela chamada real do seu framework.
    print(f"[API] Buscando dados de coletores globais para o AS{asn}...")
    return []


# -----------------------------------------------------------------------------
# AUXILIAR: ALGORITMO DE TRIMMING CONFORME A EQUAÇÃO DA LITERATURA
# -----------------------------------------------------------------------------
def _apply_alpha_trimming(scores: list[float], alpha: float) -> float:
    """
    Aplica a ordenação crescente e o corte simétrico (Alpha-Trimming)[cite: 124, 129].
    Inclui o mecanismo de salvaguarda caso a amostragem de dados positivos 
    seja menor que o tamanho da janela de poda.
    """
    if not scores:
        return 0.0
        
    scores.sort()  # BC_(1) <= BC_(2) <= ... <= BC_(n) [cite: 129]
    n = len(scores)
    k = math.floor(alpha * n)  # \lfloor \alpha n \rfloor [cite: 124]
    
    non_zero_vps = sum(1 for s in scores if s > 0.0)
    
    # Se a poda descartar todos os sinais válidos de trânsito devido à esparsidade,
    # fazemos o fallback para a média simples de modo a preservar os dados reais.
    if n - 2 * k <= 0 or non_zero_vps <= k:
        return float(np.mean(scores))
        
    trimmed_scores = scores[k : n - k]
    return sum(trimmed_scores) / len(trimmed_scores)


# =============================================================================
# ALGORITMO CORE: CÁLCULO DE HEGEMONIA (Viewpoint = Cada Peer Individual)
# =============================================================================
def calculate_as_hegemony(all_stats: list[BGPDumpSnapshotStats], target_asn: int = None, alpha=0.1) -> dict:
    """
    Mapeia os caminhos considerando cada Peer BGP individual como um Viewpoint[cite: 122].
    - Se target_asn for fornecido: Constrói um 'Local Graph' focado no destino[cite: 110].
    - Se target_asn for None: Constrói um 'Global Graph' abrangendo toda a malha[cite: 106].
    Funciona de maneira nativa e idêntica para IPv4 e IPv6.
    """
    vp_total_paths = defaultdict(int)
    vp_transit_counts = defaultdict(lambda: defaultdict(int))
    all_transit_asns = set()
    all_active_peers = set()

    # Itera sobre cada snapshot/coletor de dados fornecido
    for idx, snapshot in enumerate(all_stats):
        # Cada peer contido no mapeamento é tratado isoladamente como um Viewpoint (literatura pura) [cite: 122]
        for peer_vp, mappings in snapshot.mappings.items():
            # Geramos um identificador único de Viewpoint para evitar colisões entre snapshots diferentes
            unique_vp_key = f"Snap_{idx}_Peer_{peer_vp}"
            
            for mapping in mappings:
                as_path = mapping.get("as_path", [])
                if not as_path:
                    continue
                
                # Se houver um target_asn configurado, filtramos apenas caminhos cujo DESTINO final é o alvo [cite: 110]
                if target_asn is not None and as_path[-1] != target_asn:
                    continue
                
                vp_total_paths[unique_vp_key] += 1
                all_active_peers.add(unique_vp_key)
                
                unique_transits = set(as_path)
                
                # Se for análise de destino (Local Graph), removemos o próprio nó alvo para avaliar os trânsitos [cite: 112]
                if target_asn is not None and target_asn in unique_transits:
                    unique_transits.remove(target_asn)
                
                for transit_node in unique_transits:
                    vp_transit_counts[transit_node][unique_vp_key] += 1
                    all_transit_asns.add(transit_node)

    hegemony_scores = {}
    n_viewpoints = len(all_active_peers)
    print(f"[HEGEMONY] Total de {n_viewpoints} viewpoints (peers BGP ativos) identificados para o cálculo.")

    if n_viewpoints == 0:
        return hegemony_scores

    # Calcula a fração de centralidade por peer e aplica a agregação com trimming [cite: 121, 123]
    for asn in all_transit_asns:
        scores = []
        for vp_key in all_active_peers:
            # Fração de caminhos do viewpoint que cruzam o nó transitário [cite: 122, 129]
            fraction = vp_transit_counts[asn][vp_key] / vp_total_paths[vp_key] if vp_total_paths[vp_key] > 0 else 0.0
            scores.append(fraction)
            
        hegemony_scores[asn] = _apply_alpha_trimming(scores, alpha)

    return hegemony_scores


def bview_hegemony_of_current_ixp(all_required_data):

    config = all_required_data.get("config", {})
    ip_version = get_ip_version(config)
    subfolder = "hegemony_for_ixp"

    caida_data = all_required_data.get("caida_data")
 
    all_stats, _, _ = all_required_data["timeline"]

    last_data = all_stats[-1]
    
    user_input = input("\nDigite o ASN alvo (Origin AS) para criar um GRAFO LOCAL ou ENTER para GRAFO GLOBAL: ").strip()
    target_asn = int(user_input) if user_input else None

    alpha_value = 0.34
    hegemony_data = calculate_as_hegemony([last_data], target_asn=target_asn, alpha=alpha_value)
    
    plot_top5_transit(hegemony_data, caida_data, target_asn, ip_version, subfolder,
                      extra_label=f"For {config.get("name")}")


def bview_as_hegemony_analysis(all_required_data):
    config = all_required_data.get("config", {})


    caida_data = all_required_data.get("caida_data")


    first_dates_of_all_routeviews = all_required_data.get("all_routeviews_timelines_first_date", {})

    ip_version = get_ip_version(config)
    subfolder = "hegemony_analysis_pure"
    
    print("\n" + "="*80)
    print("SELEÇÃO DE ESTRATÉGIA DE DADOS (MÉTODO AS HEGEMONY)")
    print("="*80)
    print(f"1 - Usar todos os primeiros snapshots dos IXPs locais ({len(first_dates_of_all_routeviews)} IXPs)")
    print(first_dates_of_all_routeviews.keys())
    print("2 - Buscar dados de coletores filtrados por um AS específico")
    
    escolha_dados = input("Escolha a opção de origem de dados (1 ou 2): ").strip()
    
    total_stats = []
    
    if escolha_dados == "2":
        coletor_asn = input("Digite o ASN para o qual deseja buscar dados de coletores: ").strip()
        use_routeserver = input("Deseja buscar dados de RouteServers (sim/não)? ").strip().lower() == "sim"
        if coletor_asn:
            total_stats, _ = load_bview_asn_data_timeline_from_configs(config, int(coletor_asn), ip_version=ip_version, load_from_routeviews=use_routeserver)
            #stat: BGPDumpSnapshotStats = total_stats[0] if total_stats else None
            #if stat:
                
        else:
            print("[Erro] ASN do coletor não informado. Abortando.")
            return
    else:
        # Padrão: Extrai o primeiro snapshot de cada timeline de IXP disponível
        print("[INFO] Carregando dados a partir dos snapshots dos IXPs...")
        for config_name, snapshot in first_dates_of_all_routeviews.items():
            if snapshot and len(snapshot) > 0:
                total_stats.append(snapshot[0])

    if not total_stats:
        print("[Erro] Nenhum conjunto de dados ou snapshot válido pôde ser carregado.")
        return

    # Escolha do Origin AS para a criação do Grafo Local (Filtro de Destino)
    user_input = input("\nDigite o ASN alvo (Origin AS) para criar um GRAFO LOCAL ou ENTER para GRAFO GLOBAL: ").strip()
    target_asn = int(user_input) if user_input else None
 
    alpha_value = 0.34

    print("\n" + "="*80)
    print(f"EXECUTANDO ANÁLISE DE HEGEMONIA (IP{ip_version})") 
    print("="*80) 

    # Execução unificada baseada estritamente em viewpoints por Peer BGP [cite: 122]
    hegemony_data = calculate_as_hegemony(total_stats, target_asn=target_asn, alpha=alpha_value)

    if not hegemony_data:
        print("  -> Dados insuficientes obtidos ou zerados pelo corte estatístico de cauda.")
        return 

    plot_top5_transit(hegemony_data, caida_data, target_asn, ip_version, subfolder)


def get_sorted_asns_from_scores(hegemony_data):
    return sorted(hegemony_data.keys(), key=lambda asn: hegemony_data[asn], reverse=True)

    
def plot_top5_transit(hegemony_data, caida_data, target_asn, ip_version, subfolder, extra_label=""):

    label = f"Grafo Local -> Destino AS{target_asn}" if target_asn else "Grafo Global"
    sorted_asns = get_sorted_asns_from_scores(hegemony_data)
    top_5 = sorted_asns[:5]
    
    print(f"\n[RANKING TOP 5] ASes mais Centrais encontrados:")
    for rank, asn in enumerate(top_5, 1):
        print(f"  {rank}. AS{asn} -> Score de Hegemonia: {hegemony_data[asn]:.4f}")

    top_5_info = [get_asinfo_from_asn(caida_data, asn) for asn in top_5] if caida_data else None
    top_5_names = [
        get_formatted_asn_name(
        info["name"]) for info in top_5_info] if top_5_info else None

    top_5_info_scope = [info["info_scope"] for info in top_5_info] if top_5_info else None

    group_colors, color_to_group = create_colors_for_groups(top_5_info_scope,
                                                            overrides={
                                                                "Global": "lightblue",
                                                                "South America": "orange",
                                                                "Regional": "purple"
                                                            })
    print(group_colors, color_to_group) 
    plot_list_as_bar_plot(
        top_5_names if top_5_names else top_5,  
        [hegemony_data[asn] for asn in top_5], 
        extra_labels=[f"AS{asn}" for asn in top_5] if top_5_names else None,
        title=f'Top Transits - {label} (IP{ip_version}) {extra_label}', 
        xlabel='Transit ASN',   
        colors=group_colors if len(group_colors) > 1 else None,
        color_labels=color_to_group if len(group_colors) > 1 else None, 
        ylabel='AS Hegemony Score (0.0 - 1.0)', 
        subfolder=subfolder
    ) 


#def bview_compare_start_and_end_hegemony(all_required_data):
#    pass