# Production Dockerfile for Render (optimized)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed) and cleanup in single layer
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # Add any system packages here if needed
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy only requirements first (Docker cache optimization)
COPY requirements.txt .

# Install Python dependencies with no-cache-dir
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Non-root user for security (optional but recommended)
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Health check endpoint (for Render)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:10000/healthz').read()"

# Production entrypoint
CMD ["python", "-m", "main_render"]

