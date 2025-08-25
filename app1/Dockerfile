# Excel Data Generator Application
FROM trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11

WORKDIR /app

# Copy only requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create output directory
RUN mkdir -p /app/output

# Copy only source code (not everything)
COPY src/ ./src/
COPY *.py ./

# Fix permissions (user already exists in base image)
RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_NAME=excel-generator

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "src/excel_generator.py"]

LABEL maintainer="CI/CD Pipeline" \
      description="Excel Data Generator Application" \
      version="${APP_VERSION}" \
      app.name="app1" \
      app.type="excel-generator" \
      app.version="${APP_VERSION}" \
      build.number="${BUILD_NUMBER}" \
      git.commit="${GIT_COMMIT}" \
      git.branch="${GIT_BRANCH}" \
      build.timestamp="${BUILD_TIMESTAMP}"