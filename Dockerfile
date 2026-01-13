FROM registry.werf.io/werf/werf:2-stable AS werf-source

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=werf-source /usr/local/bin/werf /usr/local/bin/werf

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN mkdir -p /app/cache

ENTRYPOINT ["python", "main.py"]