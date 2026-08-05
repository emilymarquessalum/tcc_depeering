import json
import os
import sys
from types import NoneType
import pandas as pd 
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm
import duckdb

columns_to_read = [0, 1, 2, 11, 12]
column_names = ["CNPJ Basico", "CNPJ Ordem", "CNPJ DV", "CNAE Principal", "CNAE Secundario"]



cnae_codes_mapped = {
     "6190601": {"name": "provedor de acesso a internet", "mapped_to": "isp", "example": "COGENT Brasil"},
     "6120501": {"name": "provedor de serviços de telefonia móvel", "mapped_to": "isp",
                 "example": "Claro"},  
     "6110803": {"name": "Serviços de comunicação multimídia - SCM", "mapped_to": "SCM",
                 "example": "TATA COMMUNICATIONS",
                 "explanation": "De acordo com a Anatel isso não deveria ser diferenciado... mas discordo"
                 },
    "6204000": {
        "name": "Consultoria em tecnologia da informação",
        "mapped_to": "",
        "example": "RNP"
    },
    "6190699": {
        "name": "Outras atividades de telecomunicações não especificadas anteriormente",
        "mapped_to": "",
        "example": "America Latina Telecomunicacoes Avancadas LTDA"
    },
    "6110801": {
        "name": "Serviço de telefonia fixa", 
    },
    "6311900": {
         "name":"Tratamento de dados, provedores de serviços de aplicação e serviços de hospedagem na internet"
    }
}


output_parquet = "/home/emily/Desktop/projects/furg/tcc_depeering/src/services/receita_federal/cnpj_to_cnae_mapping.parquet"

def process_and_save_to_parquet():
    cnpj_files_to_read = ["cnpj_info_0.ESTABELE", "cnpj_info_1.ESTABELE",
                           "cnpj_info_2.ESTABELE",  "cnpj_info_3.ESTABELE",
                           "cnpj_info_4.ESTABELE","cnpj_info_5.ESTABELE",
                           "cnpj_info_6.ESTABELE",
                           "cnpj_info_7.ESTABELE","cnpj_info_8.ESTABELE","cnpj_info_9.ESTABELE",
                          ]  
    

    schema = pa.schema(
        [ 
            ("CNPJ", pa.string()),
            ("CNAE Principal", pa.string()),
            ("CNAE Secundario", pa.string()),
        ]
    )

    # Open the Parquet file for incremental writing
    with pq.ParquetWriter(
        output_parquet, schema, compression="snappy"
    ) as writer:
        total_processed_cnpjs = 0

        for cnpj_file in cnpj_files_to_read:
            if not os.path.exists(cnpj_file):
                print(f"Warning: File {cnpj_file} not found. Skipping.")
                continue

            chunk_size = 100000
            kb_per_line = 0.4
            chunk_size_in_kb = chunk_size * kb_per_line
            file_kb_size = os.path.getsize(cnpj_file) / 1024
            total_expected_chunks = int(file_kb_size / chunk_size_in_kb) + 1

            cnpj_map = pd.read_csv(
                cnpj_file,
                chunksize=chunk_size,
                usecols=columns_to_read,
                names=column_names,
                sep=";",
                encoding="latin-1",
                header=None,
                dtype=str,
            )

            for chunk in tqdm(
                cnpj_map,
                desc=f"Streaming {cnpj_file} to Parquet",
                unit="chunk",
                total=total_expected_chunks,
            ):
                if chunk.empty:
                    continue

                # 1. Vectorized CNPJ construction
                chunk["CNPJ"] = (
                    chunk["CNPJ Basico"].str.zfill(8)
                    + chunk["CNPJ Ordem"].str.zfill(4)
                    + chunk["CNPJ DV"].str.zfill(2)
                )

                # 2. Keep only the 3 columns we need
                chunk_cleaned = chunk[
                    ["CNPJ", "CNAE Principal", "CNAE Secundario"]
                ]

                # 3. Track count
                total_processed_cnpjs += len(chunk_cleaned)

                # 4. Convert Pandas chunk to Arrow Table and write immediately to disk
                table = pa.Table.from_pandas(
                    chunk_cleaned, schema=schema, preserve_index=False
                )
                writer.write_table(table)

    print(
        f"Done! {total_processed_cnpjs} CNPJs processed and streamed safely to disk."
    )
 

''' # crashes for a big file, not using it anymore
def get_cnpj_to_cnae_mapping():
    # Load the Parquet file and immediately set CNPJ as the index
    print("Loading Parquet mapping into memory...")
    df = pd.read_parquet(output_parquet)
    df.set_index("CNPJ", inplace=True)
    return df
def get_cnpj_to_cnae_mapping(): 
    table = pq.read_table(output_parquet, columns=["CNPJ", "CNAE Principal"]) 
    return dict(zip(table["CNPJ"].to_pylist(), table["CNAE Principal"].to_pylist()))
'''

def get_cnae_for_cnpj(cnpj_value):
    # This queries the file directly on your hard drive. 0% RAM pressure.
    result = duckdb.query(
        f'SELECT "CNAE Principal" FROM \'{output_parquet}\' WHERE CNPJ = \'{cnpj_value}\''
    ).fetchone() 
    
    return result[0] if result else None



 
if __name__ == "__main__":
    
    #process_and_save_to_parquet()
 
    #sys.exit(0)  

    cnpjs_to_search = [("29.484.413/0001-70", "COGENT BRASIL"),
                    ("03.508.097/0001-36", "RNP")]

    for cnpj_info in cnpjs_to_search:
        cnpj_to_search_clean = cnpj_info[0].replace(".", "").replace("/", "").replace("-", "")
        company_name = cnpj_info[1]

        #map_result = search_cnpj_in_mapping(cnpj_to_search_clean, full_cnpj_to_cnae_map)
        
        result_cnae = get_cnae_for_cnpj(cnpj_to_search_clean)

        
        print(f"  Company Name: {company_name}")
        print(f"CNPJ: {cnpj_to_search_clean}")

        print(result_cnae)
        sys.exit(0)
        if not map_result.empty:
            cnae_principal = map_result["CNAE Principal"]
            #cnae_secundario = map_result["CNAE Secundario"]

            mapped_cnae_principal = cnae_codes_mapped.get(cnae_principal, "unknown")
            #mapped_cnae_secundario = cnae_codes_mapped.get(cnae_secundario, "unknown")

            
            print(f"  CNAE Principal: {cnae_principal} -> Mapped: {mapped_cnae_principal}")
            #print(f"  CNAE Secundario: {cnae_secundario} -> Mapped: {mapped_cnae_secundario}")
           

