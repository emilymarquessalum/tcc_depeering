

from datetime import datetime
import json
import os
from scrape_vpps import scrape_vpps


def save_timestamped_vpps():
    # Record execution timestamp
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    iso_timestamp = timestamp.isoformat()

    print(f"[{iso_timestamp}] Running scraper...")
    data = scrape_vpps()

    # Inject metadata including the timestamp
    output_data = {
        "scraped_at": iso_timestamp,
        "data": data,
    }

    # Generate filename with timestamp
    filename = f"google_vpps_{timestamp_str}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Data successfully saved to {output_path}")


if __name__ == "__main__":
    save_timestamped_vpps()

 