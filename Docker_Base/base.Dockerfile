# Our company's standard Python 3.11 image with build tools
FROM python:3.11-slim

# Install system dependencies needed by our applications
# This layer will only be rebuilt when this file changes
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    # Add any other common system dependencies here
    && rm -rf /var/lib/apt/lists/*

# (Optional) You can also create the non-root user here
RUN useradd -m -u 1000 appuser