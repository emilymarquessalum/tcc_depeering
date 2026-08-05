

import json
import os

import re
import urllib.request

import requests


def download_txt_from_path(path_url_str):

  cache_path = path_url_str.split("/")[-1]
  if not cache_path.endswith(".txt"):
    cache_path += ".txt"

  if not os.path.exists(cache_path):
    print(f"Downloading {path_url_str}...")
    urllib.request.urlretrieve(path_url_str, cache_path)
    print("Download complete.")

  return cache_path


def download_google_drive_json(share_url):
    file_id_match = re.search(r"/d/([a-zA-Z0-9-_]+)", share_url)
    if not file_id_match:
        raise ValueError("Could not find a valid Google Drive file ID in the URL.")

    file_id = file_id_match.group(1)
    download_url = f"https://docs.google.com/uc?export=download&id={file_id}"

    print("Downloading file from Google Drive...")
    response = requests.get(download_url)

    if response.status_code != 200:
        raise Exception(
            f"Failed to download file. Status code: {response.status_code}"
        )
    print("Download complete.")
    return json.loads(response.content)

