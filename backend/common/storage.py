from functools import lru_cache

import boto3

from common.config import Settings, get_settings


class Storage:
    """thin wrapper over an s3 bucket so callers never touch boto3 directly."""

    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def upload_bytes(self, key: str, data: bytes, content_type: str = "text/csv") -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def download_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()


def _build_client(settings: Settings):
    kwargs: dict = {"region_name": settings.s3_region}
    # endpoint url is set for minio locally, left empty for real aws
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    # explicit keys for minio, otherwise boto3 falls back to the iam role
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    return Storage(_build_client(settings), settings.s3_bucket)
