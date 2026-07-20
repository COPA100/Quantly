from unittest.mock import MagicMock

from common.config import Settings
from common.storage import Storage, _build_client


def test_upload_bytes_calls_put_object():
    client = MagicMock()
    Storage(client, "mybucket").upload_bytes("k/1.csv", b"hello")
    client.put_object.assert_called_once_with(
        Bucket="mybucket", Key="k/1.csv", Body=b"hello", ContentType="text/csv"
    )


def test_download_bytes_reads_the_body():
    client = MagicMock()
    client.get_object.return_value = {"Body": MagicMock(read=lambda: b"data")}
    result = Storage(client, "mybucket").download_bytes("k/1.csv")
    assert result == b"data"
    client.get_object.assert_called_once_with(Bucket="mybucket", Key="k/1.csv")


def test_build_client_passes_minio_endpoint_and_keys(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "common.storage.boto3.client",
        lambda service, **kwargs: captured.update(service=service, **kwargs),
    )
    _build_client(
        Settings(
            s3_endpoint_url="http://localhost:9000",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )
    )
    assert captured["service"] == "s3"
    assert captured["endpoint_url"] == "http://localhost:9000"
    assert captured["aws_access_key_id"] == "key"


def test_build_client_omits_endpoint_and_keys_for_real_aws(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "common.storage.boto3.client",
        lambda service, **kwargs: captured.update(kwargs),
    )
    _build_client(
        Settings(s3_endpoint_url=None, aws_access_key_id=None, aws_secret_access_key=None)
    )
    # with no endpoint/keys, boto3 falls back to aws + the iam role
    assert "endpoint_url" not in captured
    assert "aws_access_key_id" not in captured
