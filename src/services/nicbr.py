
 
from pathlib import Path
import sys

import pandas as pd 

from src.utils.file_parsing import download_txt_from_path



sys.path.insert(0, str(Path(__file__).parent.parent.parent))  

from src.ripe_bviews.timeline.as_info_type.bview_info_type_graphs import plot_categories_from_ipverse_data
from src.services.as_info import get_asn_lookup_from_ipverse, get_asn_type_from_ipverse


url_prefix_to_asn_nic_mapping = "https://ftp.registro.br/pub/numeracao/origin/nicbr-asn-blk-latest.txt"




def get_prefix_to_asn_mapping_data():

  header = ["ASN", "OrgName", "OrgID", "prefixes"]

  cache_path_name_prefix_to_asn_mapping = download_txt_from_path(url_prefix_to_asn_nic_mapping)

  data = []

  with open(cache_path_name_prefix_to_asn_mapping, "r") as f:
    for line in f:
        parts = line.strip().split("|")
        row = parts[:3]
        prefixes_list = parts[3:]
        row.append(prefixes_list)
        data.append(row)

  prefix_to_asn_nic_mapping_df = pd.DataFrame(data, columns=header)
  prefix_to_asn_nic_mapping_df['ASN'] = prefix_to_asn_nic_mapping_df['ASN'].str.replace("AS", "", regex=False)
  return prefix_to_asn_nic_mapping_df



def get_asns_nicbr_has(prefix_to_asn_nic_mapping_df=None) -> list[int]:

  if prefix_to_asn_nic_mapping_df == None:
    prefix_to_asn_nic_mapping_df = get_prefix_to_asn_mapping_data()

  asns_nicbr_has = prefix_to_asn_nic_mapping_df["ASN"].astype(int).explode().unique()
  return asns_nicbr_has 

def get_cnpj_from_asn(prefix_to_asn_nic_mapping_df, asn: int):

  assert(len(prefix_to_asn_nic_mapping_df) > 0)
  
  try:
    result_filter = prefix_to_asn_nic_mapping_df[prefix_to_asn_nic_mapping_df["ASN"].astype(int) == asn]["OrgID"]
    if result_filter.shape[0] == 0: 
      return None
    return result_filter.iloc[0]
  except Exception as e:
    print(e)
    return None



import json

if __name__ == "__main__":

  
  prefix_to_asn_nic_mapping_df = get_prefix_to_asn_mapping_data()
  
  print(get_cnpj_from_asn(prefix_to_asn_nic_mapping_df, 264213))
  

  with open("/home/emily/Desktop/projects/furg/tcc_depeering/src/services/nic_missing_category_asns.json", "r") as f:
   
    ases_that_i_cant_find_types_for_supposedly = json.load(f)


  asn_lookup = get_asn_lookup_from_ipverse()
  
  type_matching_simple = [get_asn_type_from_ipverse(asn_lookup, a) for a in ases_that_i_cant_find_types_for_supposedly]
  
  plot_categories_from_ipverse_data(
    type_matching_simple,
    "Missing Category Supposedly", "--" 
  )
  # refine_ipverse_info_list_simplified