


import requests
from bs4 import BeautifulSoup

url = "https://www.ris.ripe.net/peerlist/all.shtml"

# Set a custom User-Agent header to avoid potential request blocking
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
response.raise_for_status()  # Check for HTTP errors

soup = BeautifulSoup(response.text, "html.parser")

# Extract text from all <h2> tags
h2_texts = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]

# Print extracted titles
for index, text in enumerate(h2_texts, start=1):
    print(f"{index}. {text}")

    