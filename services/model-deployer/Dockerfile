FROM python:3.9-slim

RUN apt-get update && apt-get install -y curl libxcb1 libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar -xz --strip-components=1 -C /usr/local/bin/ docker/docker

RUN curl -fsSL \
    "https://github.com/nuclio/nuclio/releases/download/1.15.9/nuctl-1.15.9-linux-amd64" \
    -o /usr/local/bin/nuctl && chmod +x /usr/local/bin/nuctl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY . .

RUN chmod +x entrypoint.sh
COPY bootstrap/ /bootstrap/

CMD ["./entrypoint.sh"]
