FROM moby/buildkit:rootless

USER root
COPY ca.crt* /usr/local/share/ca-certificates/registry.crt
RUN cat /usr/local/share/ca-certificates/registry.crt >> /etc/ssl/certs/ca-certificates.crt

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 git

ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

USER 1000:1000

ENTRYPOINT ["python", "main.py"]