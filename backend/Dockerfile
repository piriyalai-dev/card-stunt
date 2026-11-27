FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps: libpq-dev สำหรับ asyncpg, build-essential สำหรับ bcrypt/cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

COPY --chown=appuser:appuser . .

# commit ที่ build image นี้ — pull_all.sh / setup.sh ส่ง IMAGE_TAG เข้ามา
# วางหลัง COPY เพื่อให้ชั้น apt/pip cache ไม่แตกทุก commit
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
