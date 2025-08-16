# Excel Data Generator Application
# Specialized container for generating Excel files with business data

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Excel processing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create output directory for Excel files
RUN mkdir -p /app/output

# Copy application files
COPY . .

# Set permissions for Python scripts
RUN chmod +x src/*.py

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_NAME=excel-generator

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pandas, openpyxl, numpy; print('Dependencies OK')" || exit 1

# Default command runs the Excel generator
CMD ["python", "src/excel_generator.py"]

# Labels for container metadata
LABEL maintainer="CI/CD Pipeline"
LABEL description="Excel Data Generator Application"
LABEL version="1.0.0"
LABEL app.name="app1"
LABEL app.type="excel-generator"
