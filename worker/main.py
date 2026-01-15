import os
import time
import uuid
import wave
import math
import struct

import boto3
import requests

STEMS = ["vocals", "drums", "bass", "guitar", "piano", "shizzle"]
STATUSES = [
    "leased",
    "downloading",
    "processing_local",
    "uploaded_source",
    "runpod_processing",
    "uploaded_outputs",
    "outputs_ready",
]


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name=os.environ["MINIO_REGION"],
    )


def create_wav(path: str, duration_s: float = 1.0, freq: float = 440.0) -> None:
    sample_rate = 44100
    num_samples = int(sample_rate * duration_s)
    with wave.open(path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(num_samples):
            value = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
            wav_file.writeframes(struct.pack("<h", value))


def update_status(control_plane_url: str, job_id: str, status: str, message: str) -> None:
    event_id = str(uuid.uuid4())
    requests.post(
        f"{control_plane_url}/worker/update",
        json={
            "job_id": job_id,
            "event_id": event_id,
            "status": status,
            "message": message,
        },
        timeout=10,
    )


def process_job(control_plane_url: str, job: dict) -> None:
    s3_client = get_s3_client()
    bucket = os.environ["MINIO_BUCKET"]
    job_id = job["job_id"]

    update_status(control_plane_url, job_id, "downloading", "downloaded source")
    source_key = f"karaoke/in/{job_id}/source.mp4"
    s3_client.put_object(
        Bucket=bucket,
        Key=source_key,
        Body=b"dummy mp4",
        ContentType="video/mp4",
    )
    update_status(control_plane_url, job_id, "uploaded_source", "uploaded source")

    update_status(control_plane_url, job_id, "processing_local", "processing local")
    update_status(control_plane_url, job_id, "runpod_processing", "runpod simulated")

    for stem in STEMS:
        wav_key = f"karaoke/out/{job_id}/stems/{stem}.wav"
        wav_path = f"/tmp/{stem}.wav"
        create_wav(wav_path, duration_s=1.0, freq=220.0)
        with open(wav_path, "rb") as handle:
            s3_client.put_object(
                Bucket=bucket,
                Key=wav_key,
                Body=handle.read(),
                ContentType="audio/wav",
            )
    update_status(control_plane_url, job_id, "uploaded_outputs", "uploaded outputs")
    update_status(control_plane_url, job_id, "outputs_ready", "outputs ready")


def main():
    control_plane_url = os.environ["CONTROL_PLANE_URL"]
    while True:
        response = requests.post(f"{control_plane_url}/worker/lease", timeout=10)
        response.raise_for_status()
        payload = response.json()
        job = payload.get("job")
        if not job:
            time.sleep(2)
            continue
        process_job(control_plane_url, job)


if __name__ == "__main__":
    main()
