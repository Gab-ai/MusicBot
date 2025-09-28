# Dockerfile (for Railway)
FROM python:3.11-slim

# Set a working dir
WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install system deps (ffmpeg + ca-certs) then install python deps.
# Combine into one RUN to keep layers small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    \
    && python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    \
    # Install yt-dlp from PyPI pre-releases (gets dev/nightly builds)
    && pip install --no-cache-dir --upgrade --pre "yt-dlp[default]"

# Copy the rest of the app
COPY . .

# Replace with how you run your app (example)
CMD ["python", "app.py"]
