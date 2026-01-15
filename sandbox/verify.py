import os
import sys
import time

import boto3
import requests

STEMS = ["vocals", "drums", "bass", "guitar", "piano", "shizzle"]


def main() -> None:
    if len(sys.argv) < 2:
        print("missing job id", file=sys.stderr)
        sys.exit(1)

    job_id = sys.argv[1]
    control_plane_url = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8000")
    minio_endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    minio_user = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    minio_password = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_region = os.environ.get("MINIO_REGION", "us-east-1")
    bucket = os.environ.get("MINIO_BUCKET", "karaoke")

    s3_client = boto3.client(
        "s3",
        endpoint_url=minio_endpoint,
        aws_access_key_id=minio_user,
        aws_secret_access_key=minio_password,
        region_name=minio_region,
    )

    slug = None
    for _ in range(60):
        response = requests.get(f"{control_plane_url}/jobs/{job_id}", timeout=10)
        response.raise_for_status()
        payload = response.json()
        slug = payload["slug"]
        if payload["status"] == "outputs_ready":
            break
        time.sleep(2)
    else:
        print("timed out waiting for outputs_ready", file=sys.stderr)
        sys.exit(1)

    publish_response = requests.post(f"{control_plane_url}/publish/{job_id}", timeout=10)
    publish_response.raise_for_status()

    expected_keys = [
        f"karaoke/pub/{slug}/stems.json",
    ] + [f"karaoke/pub/{slug}/stems/{stem}.m4a" for stem in STEMS]

    for key in expected_keys:
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            print(f"missing key: {key}: {exc}", file=sys.stderr)
            sys.exit(1)

    print("SUCCESS")


if __name__ == "__main__":
    main()
