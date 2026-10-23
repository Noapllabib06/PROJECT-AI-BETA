# Dockerfile for JARVIS AI Agent (Python Architecture v2.0)
FROM python:3.11-slim

WORKDIR /app

# Install OS dependencies for OCR, vision, and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    tesseract-ocr \
    tesseract-ocr-ind \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and configuration
COPY . .

# Expose API and UI port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run in headless server mode
CMD ["python", "-m", "src.app.main", "--host", "0.0.0.0", "--port", "8000", "--headless"]
