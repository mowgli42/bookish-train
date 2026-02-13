FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY watch_and_ingest.py .
ENTRYPOINT ["python", "-u", "watch_and_ingest.py"]
