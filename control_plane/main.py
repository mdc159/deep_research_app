import os
import uuid
from typing import Optional

import boto3
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from publish.publisher import publish_job


def get_db_conn():
    return psycopg2.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
    )


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name=os.environ["MINIO_REGION"],
    )


app = FastAPI()


class SeedJobRequest(BaseModel):
    yt_url: Optional[str] = None
    source_key: Optional[str] = None


class WorkerUpdateRequest(BaseModel):
    job_id: str
    event_id: str
    status: str
    message: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs/seed")
def seed_job(req: SeedJobRequest):
    job_id = str(uuid.uuid4())
    slug = f"job-{job_id[:8]}"
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into jobs (id, slug, status, yt_url, source_key) values (%s, %s, %s, %s, %s)",
                (job_id, slug, "queued", req.yt_url, req.source_key),
            )
    return {"job_id": job_id, "slug": slug}


@app.post("/worker/lease")
def lease_job():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, slug, yt_url, source_key from jobs where status = %s order by created_at limit 1",
                ("queued",),
            )
            row = cur.fetchone()
            if not row:
                return {"job": None}
            job_id, slug, yt_url, source_key = row
            cur.execute("update jobs set status = %s where id = %s", ("leased", job_id))
            return {
                "job": {
                    "job_id": str(job_id),
                    "slug": slug,
                    "yt_url": yt_url,
                    "source_key": source_key,
                }
            }


@app.post("/worker/update")
def worker_update(req: WorkerUpdateRequest):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into job_events (event_id, job_id, status, message) values (%s, %s, %s, %s) on conflict (event_id) do nothing",
                (req.event_id, req.job_id, req.status, req.message),
            )
            if cur.rowcount == 0:
                return {"duplicate": True}
            cur.execute("update jobs set status = %s where id = %s", (req.status, req.job_id))
    return {"duplicate": False}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, slug, status, yt_url, source_key from jobs where id = %s",
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="job not found")
            job_id, slug, status, yt_url, source_key = row
            return {
                "job_id": str(job_id),
                "slug": slug,
                "status": status,
                "yt_url": yt_url,
                "source_key": source_key,
            }


@app.post("/publish/{job_id}")
def publish(job_id: str):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, slug from jobs where id = %s",
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="job not found")
            job_id_db, slug = row
            cur.execute("update jobs set status = %s where id = %s", ("publishing", job_id_db))
    s3_client = get_s3_client()
    bucket = os.environ["MINIO_BUCKET"]
    publish_job(s3_client, bucket, str(job_id_db), slug)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("update jobs set status = %s where id = %s", ("published", job_id_db))
    return {"status": "published", "slug": slug}
