import os
from pathlib import Path
from uuid import uuid4

from app.storage import get_s3_client

file_path = Path(__file__).parent / "sample_files" / "boat.jpg"

if not file_path.is_file():
    raise FileNotFoundError(f"File not found: {file_path}")

bucket_name = os.environ.get("S3_BUCKET_NAME")

charter_id = 2
object_key = f"charters/{charter_id}/{uuid4()}.jpg"

s3 = get_s3_client()

s3.upload_file(str(file_path), bucket_name, object_key, ExtraArgs={"ContentType": "image/jpeg"})

print(f"File uploaded to {object_key}")
print(f"File URL: https://{bucket_name}.s3.amazonaws.com/{object_key}")