FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY voting-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voting-service/app.py .

EXPOSE 5003

CMD ["python", "app.py"]
