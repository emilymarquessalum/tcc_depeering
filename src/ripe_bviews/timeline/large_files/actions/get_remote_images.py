import subprocess

# Remote host & path template
# {:02d} formats integers as two digits with leading zeros (e.g., 0 -> "00", 3 -> "03")
remote_user_host = "emsalum@200.132.77.49"
base_remote_path = "/home/emsalum/tcc_depeering_elixir/data/graphs"
file_pattern = "hegemony_over_time_15169_rrc{:02d}_v4.png.png"

destination = "./"

# Loop from 0 to 20 inclusive
for i in range(21):
    filename = file_pattern.format(i)
    full_remote_src = f"{remote_user_host}:{base_remote_path}/{filename}"
    
    print(f"Downloading: {filename} ...")
    
    # Run the scp command
    result = subprocess.run(["scp", full_remote_src, destination], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"  ✓ Successfully downloaded {filename}")
    else:
        # Prints error if the file doesn't exist on the server or connection fails
        print(f"  ✗ Failed to download {filename}: {result.stderr.strip()}")