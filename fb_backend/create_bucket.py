import os

from app.storage import get_s3_client

s3 = get_s3_client()
bucket_name = os.environ.get("S3_BUCKET_NAME")

existing_buckets = {bucket["Name"] for bucket in s3.list_buckets()["Buckets"]}

if bucket_name in existing_buckets:
    print(f"Bucket {bucket_name} already exists.")
else:
    s3.create_bucket(Bucket=bucket_name)
    print(f"Bucket {bucket_name} created.")