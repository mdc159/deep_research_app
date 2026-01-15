import json
import os
import subprocess
import tempfile
from typing import List

STEMS = ["vocals", "drums", "bass", "guitar", "piano", "shizzle"]


def _download_file(s3_client, bucket: str, key: str, dest: str) -> None:
    s3_client.download_file(bucket, key, dest)


def _upload_file(s3_client, bucket: str, key: str, path: str, content_type: str) -> None:
    s3_client.upload_file(
        path,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def publish_job(s3_client, bucket: str, job_id: str, slug: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        stems_manifest = []
        for stem in STEMS:
            wav_key = f"karaoke/out/{job_id}/stems/{stem}.wav"
            wav_path = os.path.join(tmpdir, f"{stem}.wav")
            m4a_path = os.path.join(tmpdir, f"{stem}.m4a")
            _download_file(s3_client, bucket, wav_key, wav_path)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    wav_path,
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    m4a_path,
                ],
                check=True,
                capture_output=True,
            )
            m4a_key = f"karaoke/pub/{slug}/stems/{stem}.m4a"
            _upload_file(s3_client, bucket, m4a_key, m4a_path, "audio/mp4")
            stems_manifest.append({"stem": stem, "key": m4a_key})

        manifest_key = f"karaoke/pub/{slug}/stems.json"
        manifest_path = os.path.join(tmpdir, "stems.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump({"stems": stems_manifest}, handle)
        _upload_file(s3_client, bucket, manifest_key, manifest_path, "application/json")
