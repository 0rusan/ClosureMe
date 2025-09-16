import os
import json
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

with open("config.json", "r") as f:
    config = json.load(f)
    fbx_dir = config["fbx_upload_dir"]

os.makedirs(fbx_dir, exist_ok=True)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def fbx_exists_in_s3(s3_key):
    try:
        s3.head_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
        else:
            raise e

def upload_to_s3(local_path, s3_key):
    try:
        s3.upload_file(local_path, AWS_S3_BUCKET, s3_key)
        print(f"✅ 已上傳至 S3：{s3_key}")
        return True
    except ClientError as e:
        print(f"❌ 上傳失敗：{e}")
        return False

for file in os.listdir(fbx_dir):
    if file.endswith(".fbx"):
        local_path = os.path.join(fbx_dir, file)
        base_name, ext = os.path.splitext(file)

        new_file_name = f"{base_name}{ext}"

        s3_key = f"fbx/temp/{new_file_name}"

        if fbx_exists_in_s3(s3_key):
            print(f"⚠️  檔案已存在於 S3，略過：{s3_key}")
            continue

        upload_to_s3(local_path, s3_key)