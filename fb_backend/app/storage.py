import os
import boto3
from botocore.config import Config


def get_s3_client(endpoint_url: str | None = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url if endpoint_url else os.environ.get("S3_ENDPOINT_URL"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"})
    )