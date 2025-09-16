import os
import requests
import boto3
from dotenv import load_dotenv
import json
from urllib.parse import urlparse

load_dotenv()

API_URL = os.getenv("API_URL")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

with open("config.json", "r") as f:
    image_dir = json.load(f)["image_download_dir"]

os.makedirs(image_dir, exist_ok=True)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

try:
    res = requests.get(f"{API_URL}/get-pending-images")
    res.raise_for_status()
    images = res.json()
except Exception as e:
    print("❌ 無法取得圖片清單:", e)
    exit(1)

if not images:
    print("✅ 沒有待處理圖片。")
    exit(0)

downloaded_count = 0
skipped_count = 0

for img in images:
    url = img["file_path"]
    file_name = os.path.basename(urlparse(url).path)
    local_path = os.path.join(image_dir, file_name)
    upload_batch = img["upload_batch"]

    if os.path.exists(local_path):
        print(f"⚠️  已存在本地，略過下載：{file_name}")
        skipped_count += 1
        continue

    try:
        s3_key = urlparse(url).path.lstrip("/")
        s3.download_file(AWS_S3_BUCKET, s3_key, local_path)
        print(f"✅ 已下載：{file_name} (批次：{upload_batch})")
        downloaded_count += 1
    except Exception as e:
        print(f"❌ 下載失敗：{file_name}，錯誤：{e}")

print("\n📊 下載統計")
print(f"   ✅ 成功下載：{downloaded_count} 個")
print(f"   ⚠️ 已存在跳過：{skipped_count} 個")
print(f"   📂 本地資料夾：{image_dir}")