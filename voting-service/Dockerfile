FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY voting-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voting-service/app.py .
COPY voting-service/templates ./templates
COPY voting-service/static ./static

EXPOSE 5003

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5003"]
