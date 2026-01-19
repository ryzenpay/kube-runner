FROM python:3

WORKDIR /app
RUN mkdir -p /app/cache

COPY ca.crt* /usr/local/share/ca-certificates/
RUN update-ca-certificates

# https://www.redhat.com/en/blog/podman-inside-container
RUN apt-get update && apt-get install -y \
    podman \
    fuse-overlayfs \
    && rm -rf /var/lib/apt/lists/*

COPY containers.conf /etc/containers/

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENTRYPOINT ["python", "main.py"]