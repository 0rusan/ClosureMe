import os
import json
import argparse
import shutil
import tempfile
from urllib.parse import urljoin
from pathlib import Path
import boto3
from dotenv import load_dotenv

load_dotenv()
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def load_download_dir():
    with open("config.json", encoding="utf-8") as f:
        return json.load(f)["memory_download_dir"]

def download_s3(s3_key: str, dst_path: Path):
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "memory.tmp"
        s3.download_file(AWS_S3_BUCKET, s3_key, str(tmp))
        shutil.move(str(tmp), str(dst_path))

def main():
    parser = argparse.ArgumentParser(description="下載 memory 檔")
    parser.add_argument("--file-name", required=True, help="角色檔案名稱（不含副檔名）")
    args = parser.parse_args()

    file_name = args.file_name 
    s3_key = f"uploads/{file_name}_memory.txt"
    dst_file_name = f"{file_name}.txt"

    memory_dir = Path(load_download_dir())
    memory_dir.mkdir(parents=True, exist_ok=True)

    dst = memory_dir / dst_file_name

    if dst.exists():
        print(f" 檔案已存在，跳過下載：{dst}")
        return

    try:
        download_s3(s3_key, dst)
        print(f"已成功下載：{dst}")
    except Exception as e:
        print(f"下載失敗：{e}")

if __name__ == "__main__":
    main()