
from pathlib import Path
import subprocess 
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
from src.utils.graphs import plot_list_as_bar_plot, plot_stacked_bar_plot


# this could be done via "C:\Users\Anna Sales\Desktop\emilyprojects\tcc-depeering-backup\src\ripe_bviews\timeline\bview_timeline_routes.py"
# unfortunately, the script was not written with dynamic datasources in mind, so it is faster to just do a manual check (if there is ever 
# a desire to refactor the code to be cleaner and better, take this into account) 
if __name__ == "__main__":

    remote_user_host = "emsalum@200.132.77.49"
    base_remote_path = "/home/emsalum/tcc_depeering_elixir/data/"
    file_pattern = "/rrc{rrc:02d}/output_bview.{date}.0000.{ip_version}.origin_as.15169.txt"

    dates = ["20240101","20240629","20241226","20250624", "20251221"]

    for date in dates:

        values_per_rrc = []
        for i in range(21):
            values = []
            for ip_version in ["v4", "v6"]:
                #file_pattern = f"/rrc{{rrc:02d}}/output_bview.{{date}}.0000.{{ip_version}}.origin_as.15169.txt"
                filename = file_pattern.format(rrc=i, date=date, ip_version=ip_version)
                remote_file_path = f"{base_remote_path}/{filename}"
                
                # Run 'wc -l <file>' directly on the remote machine
                ssh_command = [
                    "ssh", 
                    remote_user_host, 
                    f"wc -l < {remote_file_path}"
                ]
                
                result = subprocess.run(ssh_command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    line_count = result.stdout.strip()
                    values.append(float(line_count))
                    #print(f"✓ {filename}: {line_count} lines")
                else:
                    print(f"✗ Failed to count lines for {filename}: {result.stderr.strip()}")
                    values.append(-1)

            values_per_rrc.append(values)

            if -1 in values:
                print(f"✗ Skipping comparison for RRC {i} on {date} due to previous errors.")
            else:
                v4_count, v6_count = values 
                percentage = (v6_count) / (v4_count) * 100 if v4_count != 0 else float('inf')

                print(f"RRC {i} on {date}: Percentage={percentage:.2f}% (V4: {v4_count}, V6: {v6_count})")

        plot_stacked_bar_plot(
            [[v[0] for v in values_per_rrc],
            [v[1] for v in values_per_rrc]],
            title=f"Route Count Comparison for ASN 15169 on {date}",
           x_labels=[f"RRC {i}" for i in range(21)],
            labels=["IPv4", "IPv6"],
        )