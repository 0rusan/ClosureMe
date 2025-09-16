import os
import json
import argparse
import shutil
import tempfile
from urllib.parse import urlparse
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
        return json.load(f)["profile_download_dir"]

def download_s3(profile_url: str, dst_path: Path):
    s3_key = urlparse(profile_url).path.lstrip("/")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "profile.tmp"
        s3.download_file(AWS_S3_BUCKET, s3_key, str(tmp))
        shutil.move(str(tmp), str(dst_path))

def main():
    parser = argparse.ArgumentParser(description="下載 profile 檔")
    parser.add_argument("--file-name", required=True, help="檔案名稱（不含副檔名）")
    args = parser.parse_args()

    file_name = args.file_name  
    profile_url = f"https://closureme-assets.s3.ap-east-2.amazonaws.com/uploads/{file_name}_profile.json"

    profile_dir = Path(load_download_dir())
    profile_dir.mkdir(parents=True, exist_ok=True)

    new_name = f"{file_name}.json"
    dst = profile_dir / new_name

    if dst.exists():
        print(f" 檔案已存在，跳過下載：{dst}")
        return

    try:
        download_s3(profile_url, dst)
        print(f"已下載：{dst}")
    except Exception as e:
        print(f"下載失敗：{e}")

if __name__ == "__main__":
    main()