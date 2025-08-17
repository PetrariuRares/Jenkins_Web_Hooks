FROM trialqlk1tc.jfrog.io/dockertest-docker/python-base:3.11

WORKDIR /app

# Copy only requirements first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories
RUN mkdir -p /app/output

# Copy only source code (not everything)
COPY src/ ./src/
COPY *.py ./

# Set up user and permissions
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/excel_generator.py"]

# Labels for container metadata
LABEL maintainer="CI/CD Pipeline"
LABEL description="Excel Data Generator Application"
LABEL version="1.0.0"
LABEL app.name="app1"
LABEL app.type="excel-generator"
