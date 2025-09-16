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
        return json.load(f)["voice_download_dir"]

def purge_old_wav(folder: Path):
    for f in folder.glob("*.wav"):
        f.unlink()

def download_s3(voice_url: str, dst_path: Path):
    s3_key = urlparse(voice_url).path.lstrip("/")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "voice.tmp"
        s3.download_file(AWS_S3_BUCKET, s3_key, str(tmp))
        shutil.move(str(tmp), str(dst_path))

def main():
    parser = argparse.ArgumentParser(description="下載 voice 檔")
    parser.add_argument("--url", required=True, help="S3 上的 voice URL")
    args = parser.parse_args()

    voice_dir = Path(load_download_dir())
    voice_dir.mkdir(parents=True, exist_ok=True)

    try:
        dst = voice_dir / "default.wav" 
        download_s3(args.url, dst)
        print(f"已下載：{dst}")
    except Exception as e:
        print(f"下載失敗：{e}")

if __name__ == "__main__":
    main()