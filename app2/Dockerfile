# Excel Data Processor Application
# Specialized container for processing and analyzing Excel files

FROM trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for input/output
RUN mkdir -p /app/input /app/output /app/reports

# Copy only the necessary application source code
# This improves layer caching by not copying everything (.)
COPY processor_main.py .
# If you have other source files (e.g., in a 'src' directory), copy them here
# COPY src/ ./src/

# Create non-root user and set permissions in a single layer
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command runs the Excel processor
CMD ["python", "processor_main.py"]

# Labels for container metadata
LABEL maintainer="CI/CD Pipeline"
LABEL description="Excel Data Processor and Analytics Application"
LABEL version="1.0.0"
LABEL app.name="app2"
LABEL app.type="excel-processor"