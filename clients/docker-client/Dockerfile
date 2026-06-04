FROM python:3.12-slim
WORKDIR /app
COPY docker-client/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docker-client/watch_and_ingest.py .
COPY common /app/common
ENV PYTHONPATH=/app/common
ENTRYPOINT ["python", "-u", "watch_and_ingest.py"]
