# We need Debian for Playwright (glibc), Alpine (default HA base) is not supported
FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Install Playwright browsers and system dependencies
# Removed Playwright as LoseIt sync is deprecated
# RUN playwright install --with-deps chromium

# Copy application files
COPY . /app

# Fix permissions
RUN chmod +x /app/run.sh

# Entry point
CMD [ "/app/run.sh" ]
