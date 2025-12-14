ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:14.3.1
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

# Install python3
RUN \
  apk add --no-cache \
    python3 \
    py3-pip

RUN pip install --no-cache-dir --break-system-packages fastapi uvicorn sqlmodel aiofiles python-multipart google-generativeai

WORKDIR /app

# Force cache invalidation
ENV BUILD_DATE="2025-12-14-v0.9.10"

# Copy data for add-on
COPY . /app/

RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]
