import os
import sys
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

def load_model_dir():
    with open("config.json", encoding="utf-8") as f:
        return json.load(f)["model_download_dir"]

def download_s3_model(model_url: str, dst_path: Path):
    s3_key = urlparse(model_url).path.lstrip("/")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "model.tmp"
        s3.download_file(AWS_S3_BUCKET, s3_key, str(tmp_file))
        shutil.move(str(tmp_file), str(dst_path))

def main():
    parser = argparse.ArgumentParser(description="下載 fbx 模型")
    parser.add_argument("--file-name", required=True, help="角色檔名（不含副檔名）")
    args = parser.parse_args()

    file_name = args.file_name.strip()
    base_url = "https://closureme-assets.s3.ap-east-2.amazonaws.com/uploads"
    model_url = f"{base_url}/{file_name}.fbx"

    model_dir = Path(load_model_dir())
    model_dir.mkdir(parents=True, exist_ok=True)
    dst = model_dir / "AIAgentModel.fbx"

    try:
        download_s3_model(model_url, dst)
        print(f" 已下載模型：{dst}")
    except Exception as e:
        print(f"模型下載失敗：{e}")

if __name__ == "__main__":
    main()