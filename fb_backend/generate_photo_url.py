import os

from app.db import SessionLocal
from app.models import CharterPhoto
from app.storage import get_s3_client


with SessionLocal() as session:
    photo = session.get(CharterPhoto, 1)

    if not photo:
        raise ValueError("Photo not found")

    s3_client = get_s3_client(endpoint_url=os.environ.get("S3_PUBLIC_URL"))
    photo_url = s3_client.generate_presigned_url("get_object", Params={"Bucket": os.getenv("S3_BUCKET_NAME"),
                                                                       "Key": photo.object_key}, ExpiresIn=900)
    print(photo_url)