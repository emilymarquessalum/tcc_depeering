

#!/usr/bin/env python3
"""
Script to recursively find and delete empty .txt and .json files in data/cache/
Reports which files were deleted and how many.
"""


import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))   
 
from definitions import append_root
 
 
def cleanup_empty_files():
    cache_dir = append_root("cache")
    cache_path = Path(cache_dir)
    
    # Check if directory exists
    if not cache_path.exists():
        print(f"Directory '{cache_dir}' does not exist.")
        return 0, []
    
    if not cache_path.is_dir():
        print(f"'{cache_dir}' is not a directory.")
        return 0, []
    
    files_analyzed_count = 0

    deleted_files = []
    
    # Recursively find all .txt and .json files
    for file_path in cache_path.rglob("*"):
        # Only process files, not directories
        if not file_path.is_file():
            continue
        # Check if file has .txt or .json extension
        if file_path.suffix not in [".txt", ".json"]:
            continue
        
        files_analyzed_count += 1 
        if file_path.stat().st_size <= 2000:
            
            try:
                file_path.unlink()  # Delete the file
                relative_path = file_path.relative_to(cache_path.parent)
                deleted_files.append(str(relative_path))
                print(f"Deleted: {relative_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    
    print(f"Total files analyzed: {files_analyzed_count}")
    return len(deleted_files), deleted_files


def main():
    """Main function"""
    print("=" * 60)
    print("Cleaning up empty .txt and .json files in data/cache/")
    print("=" * 60)
    print()
    
    deleted_count, deleted_files = cleanup_empty_files()
    
    print()
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"Total files deleted: {deleted_count}")
    
    if deleted_files:
        print("\nDeleted files:")
        for file_path in deleted_files:
            print(f"  - {file_path}")
    else:
        print("No empty files found to delete.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
