FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY . /app

RUN mkdir -p /app/downloads /app/temp /app/cookies \
    && chmod -R 777 /app/downloads /app/temp /app/cookies

EXPOSE 7860 6060

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
