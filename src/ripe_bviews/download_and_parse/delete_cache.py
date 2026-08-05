



import os


def delete_cached_files(folder, format):
    for file_name in os.listdir(folder):
        if file_name.endswith(format):
            file_path = os.path.join(folder, file_name)
            os.remove(file_path)
            print(f"Deleted cached file: {file_path}")


if __name__ == "__main__":

    folder = "../data/rrc03/"
    format = ".txt"
    delete_cached_files(folder, format)