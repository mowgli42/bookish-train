FROM python:3.12-slim

# Install restic
RUN apt-get update && apt-get install -y --no-install-recommends \
    restic \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY run_restic_backup.py .

ENTRYPOINT ["python", "-u", "run_restic_backup.py"]
