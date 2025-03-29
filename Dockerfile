FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create volume mount points
RUN mkdir -p /config /logs

# Set environment variables
ENV CONFIG_PATH=/config/unmonitarr_config.json
ENV STATE_FILE=/config/unmonitarr_state.json
ENV PYTHONUNBUFFERED=1

# Run as non-root user for better security
RUN useradd -m appuser
RUN chown -R appuser:appuser /app /config /logs
USER appuser

RUN mkdir -p /logs /config && \
    chown -R appuser:appuser /logs /config && \
    chmod 755 /logs /config

# Command to run the application
CMD ["python", "unmonitarr.py", "--config", "/config/unmonitarr_config.json"]
