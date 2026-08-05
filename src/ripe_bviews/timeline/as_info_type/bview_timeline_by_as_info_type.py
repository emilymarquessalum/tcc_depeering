



import json
from types import NoneType

from src.caidapeeringdb.caidapeeringdb_load import get_asns_types_peeringdb, get_types_to_asns
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.timeline.as_info_type.bview_info_type_graphs import plot_categories_from_ipverse_data
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.services.as_info import get_asn_lookup_from_ipverse, get_asn_type_from_ipverse
from src.services.caida_as2org import CAIDAAS2Org
from src.services.nicbr import get_asns_nicbr_has, get_cnpj_from_asn, get_prefix_to_asn_mapping_data
from src.services.receita_federal.read_cnpj_mapping import get_cnae_for_cnpj
from src.utils.graphs import plot_list_as_bar_plot, plot_map_as_bar_plot


peeringdb_to_ipverse_category_mapping = {
        "content": "hosting",
        "not disclosed": "unknown",
        "cable/dsl/isp": "isp",
        "government": "government_admin",
        "educational/research": "education_research",
        "enterprise": "business",
        "non-profit": "business",

}


# from the ipverse result,
# tries to improve it with: peeringdb, as2org, and finally cnpj_to_cnae
def refine_ipverse_info(ipverse_asn_lookup, ipverse_info, 
                        as2org,  cnae_mapping_count,
                        peeringdb_data,
                        asns_types_by_peeringdb,
                        prefix_to_asn_nic_mapping_df
                        ):
    
    
    asn: int = ipverse_info["asn"]
    category_found = ipverse_info["category"]

    status_result = []
    if category_found is None or category_found.lower() == "unknown":
            
            peeringdb_type = asns_types_by_peeringdb.get(asn, "Unknown").lower()
            mapped_category = peeringdb_to_ipverse_category_mapping.get(peeringdb_type, "unknown")
            category_found = mapped_category  
            status_result.append("got_type_from_peeringdb")
            if mapped_category != "unknown":
                status_result.append("got_type_from_peeringdb_and_it_wasnt_unknown")

            else:
                result = as2org.get_org_asn_from_sub_asn(asn)
                if "error" not in result:
                    parent = result['primary_asn']
                    parent_ipverse_info = get_asn_type_from_ipverse(ipverse_asn_lookup, parent)
                    if parent_ipverse_info["category"].lower() == "unknown":
                        parent_ipverse_info["category"] = peeringdb_to_ipverse_category_mapping.get(
                            get_asns_types_peeringdb(peeringdb_data, [parent], silent=True).get(parent, "unknown").lower(), "unknown"
                        )
                    
                    status_result.append("unknown_in_both_but_had_larger_org") 
                    if parent_ipverse_info["category"] != "unknown":

                        status_result.append("unknown_in_both_but_had_larger_org_that_wasnt_unknown")  
                        category_found = parent_ipverse_info["category"]
                    else:
                        if not isinstance(cnae_mapping_count, NoneType):
                            cnpj = get_cnpj_from_asn(prefix_to_asn_nic_mapping_df, asn)
                            
                            cnae_type = None 
                            if not cnpj:
                                status_result.append("asns_that_didnt_have_mapped_cnpj")   
                                print(f"ASN {asn} didnt_have_mapped_cnpj") 
                                cnae_type = "not-BR"
                            else:
                                cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
                                cnae_principal = get_cnae_for_cnpj(cnpj) 
                                if cnae_principal == None: 
                                    cnae_principal = "not-available"
                                cnae_type = cnae_principal

                            if cnae_type not in cnae_mapping_count:
                                cnae_mapping_count[cnae_type] = 0    
                            cnae_mapping_count[cnae_type] += 1 
                            print("CNAE", cnae_type)   

 
    ipverse_info["category"] = category_found

    return ipverse_info # ,status_result

def get_cnae_from_asn(asn, prefix_to_asn_nic_mapping_df):
    cnpj = get_cnpj_from_asn(prefix_to_asn_nic_mapping_df, asn)

    if cnpj == None:
        print("ASN is not in NIC.br")
        return "not-BR"
    cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
    cnae_principal = get_cnae_for_cnpj(cnpj)
    
    return cnae_principal


def refine_ipverse_info_list(
        
        ipverse_asn_lookup, ipverse_info_list, 
                        as2org,  cnae_mapping_count,
                        peeringdb_data,
                        asns_types_by_peeringdb,
                        prefix_to_asn_nic_mapping_df
):
    refined_results = []
    for ipverse_info in ipverse_info_list:
        refined_results.append(refine_ipverse_info(ipverse_asn_lookup, ipverse_info,
                                                   as2org,   cnae_mapping_count,
                        peeringdb_data,
                        asns_types_by_peeringdb,
                        prefix_to_asn_nic_mapping_df
                                                   ))
    return refined_results 

def print_ipverse_list_results(results_for_ipverse):

    number_of_found_types = 0
    number_of_unknowns = 0

    for result in results_for_ipverse:
        if result["category"].lower() == "unknown":
            number_of_unknowns +=1 
        else:
            number_of_found_types += 1

    print(f"Types found: {number_of_found_types}, and unknowns: {number_of_unknowns}")

def refine_ipverse_info_list_simplified(asn_lookup, results_for_ipverse, cnae_mapping_count, peeringdb_data):
    prefix_to_asn_nic_mapping_df = get_prefix_to_asn_mapping_data()

    as2org = CAIDAAS2Org()  

    unique_ases = [res["asn"] for res in results_for_ipverse]
    reachables_asns_types_by_peeringdb = get_asns_types_peeringdb(peeringdb_data, unique_ases,
                                                        silent=True)
    return refine_ipverse_info_list(asn_lookup, results_for_ipverse,
                                           as2org,  
                                           cnae_mapping_count,
                                           peeringdb_data, reachables_asns_types_by_peeringdb,prefix_to_asn_nic_mapping_df) 
         


def create_asn_to_astype_map(unique_ases, peeringdb_data, cnpj_mapping_dict=None):


    asn_lookup = get_asn_lookup_from_ipverse()
    
    
    results_for_members = [get_asn_type_from_ipverse(asn_lookup, a) for a in unique_ases]

    print_ipverse_list_results(results_for_members)
    results_for_members = refine_ipverse_info_list_simplified(asn_lookup, results_for_members, cnpj_mapping_dict, peeringdb_data)

    print_ipverse_list_results(results_for_members) 

    mapping = {}

    for result in results_for_members:
        mapping[result["asn"]] = result["category"]
    
    return mapping 

def analyze_bview_by_as_info_type(all_required_data): 
    
    all_stats, labels, _ = all_required_data["timeline"]
    config = all_required_data["config"]
    ip_version = get_ip_version(config)
    ixp_name = config.get("name", config.get("rrc", "unknown_ixp"))
    peeringdb_data = all_required_data["caida_data"]

    
    stats_focused: BGPDumpSnapshotStats = all_stats[0]
    
    unique_members = stats_focused.unique_members
    unique_reachables = stats_focused.unique_reachables
    asns_by_info_type = get_types_to_asns(peeringdb_data, unique_members,
                                          silent=True)
    
    asns_by_info_type = {info_type: len(asns) for info_type, asns in asns_by_info_type.items()}



    prefix_to_asn_nic_mapping_df = get_prefix_to_asn_mapping_data()
 

    plot_list_as_bar_plot(
        list(asns_by_info_type.keys()),
        list(asns_by_info_type.values()),
         title=f"{ixp_name} Member ASes, by PeeringDB Category - for {labels[0].replace('/', '_')} - {ip_version}",
          xlabel="Number of Members",
          ylabel="PeeringDB Category",
          sort_by_size=True,
          sort_by_size_cut=5
          
    )


    asn_lookup = get_asn_lookup_from_ipverse()
    
    
    results_for_members = [get_asn_type_from_ipverse(asn_lookup, a) for a in unique_members]
    categories_count_from_ipverse = {}
    
    for res in results_for_members:
        category = res["category"]
        categories_count_from_ipverse[category] = categories_count_from_ipverse.get(category, 0) + 1
    
    
    plot_list_as_bar_plot(
        [(v.capitalize() if v is not None else "Unknown") for v in list(categories_count_from_ipverse.keys())],
        list(categories_count_from_ipverse.values()),
         title=f"{ixp_name} Member ASes, by IPVerse AS Category - for {labels[0].replace('/', '_')} - {ip_version}",
          xlabel="Number of Members",
          ylabel="IPVerse AS Category",
          sort_by_size=True,
          sort_by_size_cut=5  
    )


    results_for_reachables_ipverse = [get_asn_type_from_ipverse(asn_lookup, int(a)) for a in unique_reachables]
 
    
    reachables_asns_types_by_peeringdb = get_asns_types_peeringdb(peeringdb_data, unique_reachables,
                                                        silent=True)

    
    results_matched = []
    number_of_asns_that_got_their_category_from_peeringdb = 0
    number_of_asns_that_got_their_category_from_peeringdb_and_it_wasnt_unknown = 0

    number_of_asns_with_unknown_in_both_that_had_a_larger_organization_to_map_to = 0
    number_of_asns_with_unknown_in_both_that_had_a_larger_organization_to_map_to_that_wasnt_unknown = 0
    as2org = CAIDAAS2Org()
    

    cnae_mapping_count = {} # CNAE String to number of ASes with unknown type that were mapped to that CNAE.
    asns_that_werent_from_nic = 0


    for ipverse_info in results_for_reachables_ipverse:
        

        ipverse_info = refine_ipverse_info(asn_lookup, ipverse_info,
                                           as2org, 
                                           cnae_mapping_count,
                                           peeringdb_data, reachables_asns_types_by_peeringdb,prefix_to_asn_nic_mapping_df) 
         
        results_matched.append(ipverse_info)


    print("ASes that got their type from peeringdb:", number_of_asns_that_got_their_category_from_peeringdb)
    print("ASes that got their type from peeringdb and it wasn't unknown:", number_of_asns_that_got_their_category_from_peeringdb_and_it_wasnt_unknown)
    print("ASes with unknown type in both but had a larger organization to map to:", number_of_asns_with_unknown_in_both_that_had_a_larger_organization_to_map_to)
    print("ASes with unknown type in both but had a larger organization to map to that wasn't unknown:", number_of_asns_with_unknown_in_both_that_had_a_larger_organization_to_map_to_that_wasnt_unknown)
    
    print(cnae_mapping_count) 

    plot_map_as_bar_plot(cnae_mapping_count,
                         title=f"CNAE From ASes that had type unknown - {ip_version}")

     
    plot_categories_from_ipverse_data(results_matched, f"{ixp_name} Reachables", labels,
                                      ip_version=ip_version)
 
    asn_to_asn_type_mapping = {res["asn"]: res["category"] for res in results_matched}
    file_result_name = f"{ixp_name}_asn_info_types_reachables_{labels[0].replace('/', '_')}.json"
    with open(file_result_name, 'w') as f:
        json.dump(asn_to_asn_type_mapping, f, indent=4) 
    
    print(f"Saved ASN to AS info type mapping to {file_result_name}")

