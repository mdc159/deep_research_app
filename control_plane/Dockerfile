FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY control_plane/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY control_plane /app
COPY publish /app/publish

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
