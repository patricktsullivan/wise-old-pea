# Wise Old Pea Bot - Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source code
COPY *.py ./
COPY challenge_rules.json ./

# Create directories for data and logs
RUN mkdir -p data logs

# Create non-root user for security
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('data/wise_old_pea_data.json') else 1)"

# Default command
CMD ["python", "wise_old_pea.py"]

# Labels
LABEL maintainer="Wise Old Pea Bot"
LABEL description="Discord bot for Old School RuneScape events"
LABEL version="1.0"