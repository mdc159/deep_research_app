import os
import uuid

import boto3
import requests


def ensure_bucket(s3_client, bucket: str) -> None:
    buckets = s3_client.list_buckets().get("Buckets", [])
    if not any(b["Name"] == bucket for b in buckets):
        s3_client.create_bucket(Bucket=bucket)


def main() -> None:
    control_plane_url = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8000")
    minio_endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    minio_user = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    minio_password = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_region = os.environ.get("MINIO_REGION", "us-east-1")
    bucket = os.environ.get("MINIO_BUCKET", "karaoke")
    yt_url = os.environ.get("YT_URL")

    s3_client = boto3.client(
        "s3",
        endpoint_url=minio_endpoint,
        aws_access_key_id=minio_user,
        aws_secret_access_key=minio_password,
        region_name=minio_region,
    )
    ensure_bucket(s3_client, bucket)

    source_key = f"seed/{uuid.uuid4()}.mp4"
    s3_client.put_object(
        Bucket=bucket,
        Key=source_key,
        Body=b"dummy mp4",
        ContentType="video/mp4",
    )

    response = requests.post(
        f"{control_plane_url}/jobs/seed",
        json={"yt_url": yt_url, "source_key": source_key},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    print(payload["job_id"])


if __name__ == "__main__":
    main()
