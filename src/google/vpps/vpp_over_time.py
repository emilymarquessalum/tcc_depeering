

import json

def compare_item_counts(before_file_path: str, after_file_path: str):
    # Load JSON files
    with open(before_file_path, "r", encoding="utf-8") as f:
        before_data = json.load(f)

    with open(after_file_path, "r", encoding="utf-8") as f:
        after_data = json.load(f)

    # Get all unique keys from both files
    all_keys = set(before_data.keys()).union(set(after_data.keys()))

    print(f"{'Category':<15} | {'Before':<10} | {'After':<10} | {'Diff':<10}")
    print("-" * 55)

    total_before = 0
    total_after = 0

    for key in sorted(all_keys):
        count_before = len(before_data.get(key, []))
        count_after = len(after_data.get(key, []))
        diff = count_after - count_before
        
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        
        print(f"{key:<15} | {count_before:<10} | {count_after:<10} | {diff_str:<10}")

        total_before += count_before
        total_after += count_after

    total_diff = total_after - total_before
    total_diff_str = f"+{total_diff}" if total_diff > 0 else str(total_diff)

    print("-" * 55)
    print(f"{'TOTAL':<15} | {total_before:<10} | {total_after:<10} | {total_diff_str:<10}")

if __name__ == "__main__":
    # Replace with your actual file paths
    compare_item_counts("C:\\Users\\Anna Sales\\Desktop\\emilyprojects\\tcc-depeering-backup\\src\\google\\vpps\\google_vpps_08_2026.json", "C:\\Users\\Anna Sales\\Desktop\\emilyprojects\\tcc-depeering-backup\\src\\google\\vpps\\google_vpps_10_2026.json")