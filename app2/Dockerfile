# Excel Data Processor Application
# Specialized container for processing and analyzing Excel files

FROM trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11

# Set working directory
WORKDIR /app

# Install system dependencies for data processing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for input/output
RUN mkdir -p /app/input /app/output /app/reports

# Copy application files
COPY . .

# Set permissions for Python scripts
RUN find . -name "*.py" -exec chmod +x {} \;

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV APP_NAME=excel-processor

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pandas, matplotlib, seaborn; print('Dependencies OK')" || exit 1

# Default command runs the Excel processor
CMD ["python", "processor_main.py"]

# Labels for container metadata
LABEL maintainer="CI/CD Pipeline"
LABEL description="Excel Data Processor and Analytics Application"
LABEL version="1.0.0"
LABEL app.name="app2"
LABEL app.type="excel-processor"
