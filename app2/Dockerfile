# Data Processing Application
FROM trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11

# Declare build arguments that will be passed from Jenkins
ARG APP_VERSION=unknown
ARG BUILD_NUMBER=unknown
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIMESTAMP=unknown

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/input /app/output /app/reports

# Copy application files
COPY processor_main.py .

# Fix permissions (user already exists in base image)
RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV APP_NAME=data-processor

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "processor_main.py"]

LABEL maintainer="CI/CD Pipeline" \
      description="Data Processing Application" \
      version="${APP_VERSION}" \
      app.name="app2" \
      app.type="data-processor" \
      app.version="${APP_VERSION}" \
      build.number="${BUILD_NUMBER}" \
      git.commit="${GIT_COMMIT}" \
      git.branch="${GIT_BRANCH}" \
      build.timestamp="${BUILD_TIMESTAMP}"