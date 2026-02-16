FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY frontend-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend-service/app.py .
COPY frontend-service/templates ./templates
COPY frontend-service/static ./static

EXPOSE 5000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
