# Dockerfile
FROM python:3.12-slim

# System deps for voice
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    && rm -rf /var/lib/apt/lists/*

# (Optional) make logs flush immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
    && pip install --no-cache-dir --upgrade --pre "yt-dlp[default]"
 
COPY . .

# Use a tmp path that's definitely writeable on Railway
ENV DOWNLOAD_DIR=/tmp/downloads
RUN mkdir -p $DOWNLOAD_DIR

CMD ["python", "musicbot.py"]
