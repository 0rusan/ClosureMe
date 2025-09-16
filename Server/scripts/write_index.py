import argparse
import json
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-name", required=True, help="角色名稱")
    args = parser.parse_args()

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    output_dir = config.get("index_output_dir")
    if not output_dir:
        raise ValueError("config.json 中缺少 index_output_dir")

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "index.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(args.file_name + "\n")

    print(f"index.txt 已寫入: {output_path}")

if __name__ == "__main__":
    main()