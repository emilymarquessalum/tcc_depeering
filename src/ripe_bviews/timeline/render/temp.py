

import os

import requests


URL_ELIXIR = os.getenv("URL_ELIXIR", "http://localhost:4000")


requests.get(URL_ELIXIR + "/bview/parse-and-cache/?file_path=/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/rrc15/output_bview.20240616.0000.txt")