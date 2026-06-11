FROM quay.io/nuclio/handler-builder-python-onbuild:1.13.0-amd64 AS builder
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
COPY --from=builder /opt/nuclio /opt/nuclio
RUN apt-get update && apt-get install -y \
    python3 python3-pip python-is-python3 \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir ultralytics Pillow numpy
WORKDIR /opt/nuclio
COPY main.py /opt/nuclio/main.py
