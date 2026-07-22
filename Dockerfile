FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY src/ src/
COPY templates/ templates/
COPY fonts/ fonts/
COPY sfx/ sfx/
COPY library/ library/

ENV PORT=8080
# Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_URL at deploy time.
CMD ["python", "-m", "src.telegram_bot"]
