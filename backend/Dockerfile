# --- PitchIQ backend: FastAPI served by Gunicorn + Uvicorn workers ---
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Dataset is mounted/copied to /data in the image; override with ATWC26_DATA_DIR.
ENV ATWC26_DATA_DIR=/data

# Run as non-root.
RUN useradd -m appuser
USER appuser

EXPOSE 8000

# 4 Uvicorn workers behind Gunicorn. Scale workers via $WEB_CONCURRENCY.
ENV WEB_CONCURRENCY=4
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", "--graceful-timeout", "30", \
     "--access-logfile", "-"]
