import os
import boto3
from botocore.config import Config


def get_s3_client(endpoint_url: str | None = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url if endpoint_url else os.environ.get("S3_ENDPOINT_URL"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"})
    )


def generate_photo_url(object_key: str) -> str:
    s3 = get_s3_client(endpoint_url=os.environ.get("S3_PUBLIC_URL"))

    return s3.generate_presigned_url("get_object", Params={"Bucket": os.environ.get("S3_BUCKET_NAME"),
                                                           "Key": object_key}, ExpiresIn=900)
