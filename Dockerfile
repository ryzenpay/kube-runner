FROM registry.werf.io/werf/werf:2-stable AS werf-source

FROM python:3

COPY --from=werf-source /usr/local/bin/werf /usr/local/bin/werf

WORKDIR /app
RUN mkdir -p /app/cache

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENTRYPOINT ["python", "main.py"]