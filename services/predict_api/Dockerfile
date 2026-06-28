FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/predict_api/requirements.txt ./requirements.txt
COPY packages/atwc26_core /packages/atwc26_core
RUN pip install --no-cache-dir /packages/atwc26_core && pip install --no-cache-dir -r requirements.txt

COPY services/predict_api/predict_api ./predict_api
COPY services/shared /services/shared

ENV PYTHONPATH=/app:/services \
    ATWC26_DATA_DIR=/data

RUN useradd -m appuser
USER appuser

EXPOSE 8000

ENV WEB_CONCURRENCY=2
CMD ["gunicorn", "predict_api.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", "--graceful-timeout", "30", \
     "--access-logfile", "-"]
