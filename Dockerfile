FROM python:3.11-slim

WORKDIR /app

# Добавили build-essential и python3-dev
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ build-essential python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

ENV PYTHONUNBUFFERED=1