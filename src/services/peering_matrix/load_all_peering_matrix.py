
import json

from peering_matrix import fetch_and_save_peering_matrix


if __name__ == "__main__":

    with open("./peering_load_config.json") as f:
        config = json.load(f)


    for url in config["urls"]:
        fetch_and_save_peering_matrix(url, outputs=config["outputs"])
