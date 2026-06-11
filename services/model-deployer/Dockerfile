FROM python:3.9-slim

RUN apt-get update && apt-get install -y curl libxcb1 libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL \
    "https://github.com/nuclio/nuclio/releases/download/1.15.9/nuctl-1.15.9-linux-amd64" \
    -o /usr/local/bin/nuctl && chmod +x /usr/local/bin/nuctl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
